"""Backfill historical player-prop odds from The Odds API (paid plan required), for any league.

For every game in the date range it saves two snapshots:
  bet   = --bet-minutes before tip (the price you realistically could have taken)
  close = --close-minutes before tip (the closing line, used to grade CLV)

Historical calls are billed in credits per market per region, so ALWAYS run with
--estimate first:

    python -m tipoff.backfill_odds --start 2026-01-05 --end 2026-01-11 --estimate
    python -m tipoff.backfill_odds --start 2026-01-05 --end 2026-01-11
    python -m tipoff.backfill_odds --league nfl --start 2026-10-18 --end 2026-10-20 --estimate

Check the credit costs and endpoint details against https://the-odds-api.com/liveapi/guides/v4/
before a big run; they can change.
"""
import argparse
import os
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from . import leagues
from .db import connect
from .snapshot import odds_rows, team_code

BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba"
ET = ZoneInfo("America/New_York")
DEFAULT_MARKETS = list(leagues.NBA.markets)
# hardrockbet is the one you can actually bet in Florida; the rest give a consensus fair price.
DEFAULT_BOOKS = ["hardrockbet", "draftkings", "fanduel", "betmgm", "caesars", "espnbet", "betrivers",
                 "pinnacle", "betonlineag"]  # up to 10 books still bill as one region


def _get(url, params):
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 429:
        time.sleep(5)
        r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    used, left = r.headers.get("x-requests-used"), r.headers.get("x-requests-remaining")
    return r.json(), used, left


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def base(league=None):
    return f"https://api.the-odds-api.com/v4/historical/sports/{leagues.get(league).sport_key}"


def events_on(day: date, key: str, league=None):
    # Snapshot at 8am ET lists that day's games (NFL London games kick off at 9:30am ET).
    when = datetime(day.year, day.month, day.day, 10 if leagues.get(league).id == "nba" else 8, tzinfo=ET)
    body, _, _ = _get(f"{base(league)}/events", {"apiKey": key, "date": iso(when)})
    out = []
    for e in body.get("data", []):
        tip = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if tip.astimezone(ET).date() == day:
            out.append(e)
    return out


def save_snapshot(con, event, label, when, key, markets, books, league=None):
    params = {
        "apiKey": key, "date": iso(when), "regions": "us", "oddsFormat": "american",
        "markets": ",".join(markets), "bookmakers": ",".join(books),
    }
    body, used, left = _get(f"{base(league)}/events/{event['id']}/odds", params)
    rows = odds_rows(event["id"], label, body.get("timestamp", iso(when)), body.get("data") or {})
    con.executemany("INSERT OR REPLACE INTO prop_odds VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows), left


def run(start, end, bet_minutes, close_minutes, markets, books, estimate, db_path=None, league=None):
    lg = leagues.get(league)
    markets = markets or list(lg.markets)
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise SystemExit("Set ODDS_API_KEY (see .env.example).")
    con = connect(db_path, league=lg)
    day, n_events = start, 0
    while day <= end:
        evs = events_on(day, key, lg)
        n_events += len(evs)
        print(f"{day}: {len(evs)} games")
        if not estimate:
            for e in evs:
                tip = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
                con.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?)",
                            (e["id"], e["commence_time"], str(tip.astimezone(ET).date()),
                             team_code(e["home_team"], lg), team_code(e["away_team"], lg)))
                for label, mins in (("bet", bet_minutes), ("close", close_minutes)):
                    n, left = save_snapshot(con, e, label, tip - timedelta(minutes=mins), key, markets, books, lg)
                    print(f"   {e['away_team']} @ {e['home_team']} [{label}] {n} prices  (credits left: {left})")
                con.commit()
        day += timedelta(days=1)
    # Historical event-odds pricing at time of writing: 10 credits x markets x regions per call.
    calls = n_events * 2
    print(f"\n{n_events} games -> {calls} snapshot calls, roughly {calls * 10 * len(markets):,} credits "
          f"for {len(markets)} markets (plus 1 per day for the event lists). Verify on the pricing page.")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--bet-minutes", type=int, default=60, help="snapshot used as the bet price")
    ap.add_argument("--close-minutes", type=int, default=5, help="snapshot used as the closing line")
    ap.add_argument("--markets", nargs="+", default=None, help="default: the league's prop markets")
    ap.add_argument("--books", nargs="+", default=DEFAULT_BOOKS)
    ap.add_argument("--estimate", action="store_true", help="count games and credits only")
    ap.add_argument("--db", default=None)
    leagues.add_argument(ap)
    a = ap.parse_args()
    run(a.start, a.end, a.bet_minutes, a.close_minutes, a.markets, a.books, a.estimate, a.db, a.league)
