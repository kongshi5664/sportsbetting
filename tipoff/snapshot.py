"""Live odds snapshots from The Odds API (works on the free tier; costs credits per call).

    python -m tipoff.snapshot --estimate            # tonight's games and the credit cost of one refresh
    python -m tipoff.snapshot                       # refresh every game that hasn't started
    python -m tipoff.snapshot --close               # closing snapshot for games tipping within 10 minutes
    python -m tipoff.snapshot --watch --every 30    # refresh every 30 min and take each close; stops after the last tip
    python -m tipoff.snapshot --league nfl --estimate   # the same for the NFL (data/nfl.db)

Each refresh replaces the 'live' snapshot for a game (the board always prices the latest one).
The 'close' snapshot, taken just before tip, is what bets are graded against for CLV.
Cost per game per refresh = markets x regions; our books fit in one region, so 5 credits with
the default NBA markets (6 for the NFL's). Listing the night's games is free.
"""
import argparse
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import leagues
from .db import connect, name_key
from .leagues import NBA

BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"
ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MARKETS = list(NBA.markets)
# hardrockbet is the one you can bet in Florida; the rest give a consensus fair price.
DEFAULT_BOOKS = ["hardrockbet", "draftkings", "fanduel", "betmgm", "caesars", "espnbet", "betrivers",
                 "pinnacle", "betonlineag"]  # up to 10 books still bill as one region
CLOSE_MINUTES = 5

# The Odds API names teams in full; box scores use NBA codes. Events are stored with codes so
# grading can join a bet's game to its box score.
TEAM_CODES = NBA.team_codes  # every league's codes live in tipoff/leagues.py


def base(league=None):
    return f"https://api.the-odds-api.com/v4/sports/{leagues.get(league).sport_key}"


def team_code(name, league=None):
    lg = leagues.get(league)
    code = lg.team_codes.get(name)
    if code is None:
        print(f"   ! unknown {lg.label} team name '{name}': add it to team_codes in tipoff/leagues.py")
        return name
    return code


def load_env():
    """Read .env into the environment without overriding variables already set (no extra dependency)."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition("=")
        if sep and k.strip() and not k.strip().startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key():
    load_env()
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise SystemExit("Set ODDS_API_KEY in .env (copy .env.example).")
    return key


class Credits:
    """Tracks what the API says each call cost and how many credits remain."""

    def __init__(self):
        self.used = 0
        self.remaining = None

    def note(self, r):
        self.used += int(r.headers.get("x-requests-last", 0) or 0)
        left = r.headers.get("x-requests-remaining")
        self.remaining = int(float(left)) if left else self.remaining
        if left:
            from . import status
            status.update(credits_remaining=self.remaining, credits_at=status.now())


def _get(url, params, credits):
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 429:
        time.sleep(5)
        r = requests.get(url, params=params, timeout=30)
    if r.status_code == 401:
        if "quota" in r.text.lower() or "credit" in r.text.lower():
            raise SystemExit("Out of Odds API credits for this month. Upgrade the plan or wait for the reset.")
        raise SystemExit("The Odds API rejected the key (401). Check ODDS_API_KEY in .env.")
    r.raise_for_status()
    credits.note(r)
    return r.json()


def games_on(day: date, key, credits, league=None):
    """Tonight's games (free call)."""
    start = datetime(day.year, day.month, day.day, tzinfo=ET)
    params = {"apiKey": key, "commenceTimeFrom": _iso(start), "commenceTimeTo": _iso(start + timedelta(days=1))}
    out = []
    for e in _get(f"{base(league)}/events", params, credits):
        tip = _tip(e)
        if tip.astimezone(ET).date() == day:
            out.append(e)
    return sorted(out, key=_tip)


def odds_rows(event_id, label, snap_ts, data):
    """Flatten one event's odds payload into prop_odds rows. Shared with backfill_odds."""
    rows = []
    for bk in data.get("bookmakers", []):
        for mk in bk.get("markets", []):
            for o in mk.get("outcomes", []):
                player = o.get("description")
                if not player or o.get("point") is None:
                    continue
                rows.append((event_id, label, snap_ts, bk["key"], mk["key"], player,
                             name_key(player), o["name"], float(o["point"]), int(o["price"])))
    return rows


def save_event(con, e, league=None):
    tip = _tip(e)
    con.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?)",
                (e["id"], e["commence_time"], str(tip.astimezone(ET).date()),
                 team_code(e["home_team"], league), team_code(e["away_team"], league)))


def snapshot(con, e, label, key, credits, markets=None, books=DEFAULT_BOOKS, league=None):
    """Pull one game's props now and replace its `label` snapshot. Returns rows saved.

    The day's first live pull is also kept as the game's 'open' snapshot (never overwritten), so
    the desk can show how far Hard Rock has moved since the morning. Costs nothing extra."""
    markets = markets or list(leagues.get(league).markets)
    params = {"apiKey": key, "markets": ",".join(markets), "bookmakers": ",".join(books), "oddsFormat": "american"}
    data = _get(f"{base(league)}/events/{e['id']}/odds", params, credits)
    rows = odds_rows(e["id"], label, _iso(datetime.now(timezone.utc)), data)
    save_event(con, e, league)
    if label == "live" and not con.execute("SELECT 1 FROM prop_odds WHERE event_id=? AND label='open' LIMIT 1",
                                           (e["id"],)).fetchone():
        earlier = con.execute("SELECT 1 FROM prop_odds WHERE event_id=? AND label='live' LIMIT 1", (e["id"],)).fetchone()
        if earlier:  # an earlier live pull exists: that one is the opening line
            con.execute("INSERT OR IGNORE INTO prop_odds SELECT event_id, 'open', snapshot_ts, book, market, player,"
                        " name_key, side, point, price FROM prop_odds WHERE event_id=? AND label='live'", (e["id"],))
        else:
            con.executemany("INSERT OR REPLACE INTO prop_odds VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [(r[0], "open") + r[2:] for r in rows])
    con.execute("DELETE FROM prop_odds WHERE event_id=? AND label=?", (e["id"], label))
    con.executemany("INSERT OR REPLACE INTO prop_odds VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return rows


def report_unmatched(con, rows):
    """Odds names that don't match any box-score name can't be projected; say so instead of dropping them.
    Each one is also appended to unmatched-names.log beside the database, to fix later."""
    keys = {(r[6], r[5]) for r in rows}
    known = {k for (k,) in con.execute("SELECT DISTINCT name_key FROM player_games")}
    missing = sorted(name for k, name in keys if k not in known)
    if missing:
        db_file = con.execute("PRAGMA database_list").fetchone()[2]
        if db_file:
            try:
                with open(Path(db_file).parent / "unmatched-names.log", "a", encoding="utf-8") as f:
                    stamp = _iso(datetime.now(timezone.utc))
                    f.writelines(f"{stamp}\t{Path(db_file).name}\t{n}\t{name_key(n)}\n" for n in missing)
            except OSError:
                pass
        print(f"   ! {len(missing)} players have no box-score match (check db.name_key): {', '.join(missing[:8])}"
              + (" ..." if len(missing) > 8 else ""))


def refresh(con, day, key, credits, close=False, markets=None, books=DEFAULT_BOOKS, max_credits=None,
            league=None):
    """Refresh live odds for games that haven't tipped; with close=True, take closing snapshots for
    games tipping within the next 10 minutes. Returns the number of games pulled."""
    markets = markets or list(leagues.get(league).markets)
    now = datetime.now(timezone.utc)
    pulled = 0
    for e in games_on(day, key, credits, league):
        tip = _tip(e)
        if tip <= now:
            continue
        if close and tip - now > timedelta(minutes=10):
            continue
        if max_credits is not None and credits.used + len(markets) > max_credits:
            print(f"   stopping: the next call would pass the {max_credits}-credit limit for this run")
            break
        label = "close" if close else "live"
        rows = snapshot(con, e, label, key, credits, markets, books, league)
        hr = sum(r[3] == "hardrockbet" for r in rows)
        print(f"   {team_code(e['away_team'], league)} @ {team_code(e['home_team'], league)} {tip.astimezone(ET):%I:%M%p} "
              f"[{label}] {len(rows)} prices, {hr} at Hard Rock")
        if not hr:
            print("   ! no Hard Rock prices for this game yet: nothing on it is bettable")
        report_unmatched(con, rows)
        pulled += 1
    return pulled


def watch(con, day, key, every, markets, books, max_credits, league=None):
    """Refresh every `every` minutes and take each game's close; returns after the last tip."""
    markets = markets or list(leagues.get(league).markets)
    credits = Credits()
    closed = set()
    next_refresh = datetime.now(timezone.utc)
    while True:
        now = datetime.now(timezone.utc)
        games = games_on(day, key, credits, league)
        upcoming = [e for e in games if _tip(e) > now]
        if not upcoming:
            print(f"All games have tipped. Credits used this run: {credits.used}, remaining: {credits.remaining}")
            return
        for e in upcoming:
            if e["id"] not in closed and _tip(e) - now <= timedelta(minutes=CLOSE_MINUTES):
                snapshot(con, e, "close", key, credits, markets, books, league)
                closed.add(e["id"])
                print(f"   closed {team_code(e['away_team'], league)} @ {team_code(e['home_team'], league)}")
        if now >= next_refresh:
            print(f"{now.astimezone(ET):%I:%M%p} refresh")
            refresh(con, day, key, credits, markets=markets, books=books, max_credits=max_credits, league=league)
            print(f"   credits used this run: {credits.used}, remaining: {credits.remaining}")
            next_refresh = now + timedelta(minutes=every)
        if max_credits is not None and credits.used >= max_credits:
            print(f"Reached the {max_credits}-credit limit; closing snapshots only from here.")
            next_refresh = datetime.max.replace(tzinfo=timezone.utc)
        time.sleep(60)


def estimate(day, key, markets, league=None):
    markets = markets or list(leagues.get(league).markets)
    credits = Credits()
    games = games_on(day, key, credits, league)
    now = datetime.now(timezone.utc)
    left = [e for e in games if _tip(e) > now]
    for e in games:
        tip = _tip(e)
        print(f"   {team_code(e['away_team'], league)} @ {team_code(e['home_team'], league)} {tip.astimezone(ET):%I:%M%p}"
              + ("" if tip > now else "  (started)"))
    per = len(left) * len(markets)
    print(f"\n{len(games)} games, {len(left)} not started -> about {per} credits per refresh "
          f"({len(markets)} markets x 1 region each), plus {per} for the closing snapshots.")
    print(f"Credits remaining: {credits.remaining}")


def _tip(e):
    return datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=date.fromisoformat, default=datetime.now(ET).date())
    ap.add_argument("--estimate", action="store_true", help="list games and the credit cost; spends nothing")
    ap.add_argument("--close", action="store_true", help="closing snapshot for games tipping within 10 minutes")
    ap.add_argument("--watch", action="store_true", help="keep refreshing until the last game tips")
    ap.add_argument("--every", type=int, default=30, help="minutes between refreshes in --watch")
    ap.add_argument("--max-credits", type=int, default=600, help="stop refreshing past this many credits per run")
    ap.add_argument("--markets", nargs="+", default=None, help="default: the league's prop markets")
    ap.add_argument("--books", nargs="+", default=DEFAULT_BOOKS)
    ap.add_argument("--db", default=None)
    leagues.add_argument(ap)
    a = ap.parse_args()
    key = api_key()
    if a.estimate:
        estimate(a.date, key, a.markets, a.league)
    else:
        con = connect(a.db, league=a.league)
        if a.watch:
            watch(con, a.date, key, a.every, a.markets, a.books, a.max_credits, a.league)
        else:
            c = Credits()
            n = refresh(con, a.date, key, c, close=a.close, markets=a.markets, books=a.books,
                        max_credits=a.max_credits, league=a.league)
            print(f"{n} games pulled. Credits used: {c.used}, remaining: {c.remaining}")
