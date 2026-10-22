"""Injury watcher: alerts when a player on tonight's slate changes status.

    python -m tipoff.injuries                # check once now
    python -m tipoff.injuries --watch        # every 3 minutes until the last tip tonight

Source: ESPN's public NBA injuries feed (status, short note, timestamp; no key). Alerts go to
your phone through ntfy (free app: subscribe to a private topic name and put it in .env as
NTFY_TOPIC); without a topic they print here. With an odds key, the game of the player in the
news gets a fresh odds pull (about 5 credits) so the board shows current prices.

Only changes alert. Long-term injuries already known before today stay quiet.
"""
import argparse
import os
import time
from datetime import date, datetime, timezone

import requests

from .db import connect, name_key
from .snapshot import ET, TEAM_CODES, Credits, games_on, load_env, snapshot

FEED = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
TABLE = """
CREATE TABLE IF NOT EXISTS injuries (
    name_key TEXT PRIMARY KEY,
    player   TEXT NOT NULL,
    team     TEXT NOT NULL,
    status   TEXT NOT NULL,       -- Out / Doubtful / Questionable / Day-To-Day / Probable / Active
    detail   TEXT NOT NULL,
    updated  TEXT NOT NULL,       -- when the source last changed it (ISO UTC)
    seen_at  TEXT NOT NULL        -- when this desk last saw it
);
"""
DESK_URL = os.environ.get("TIPOFF_URL", "http://127.0.0.1:8000")


def fetch():
    """Every listed NBA injury: [{name_key, player, team, status, detail, updated}]."""
    r = requests.get(FEED, timeout=20)
    r.raise_for_status()
    out = []
    for team in r.json().get("injuries", []):
        code = TEAM_CODES.get(team.get("displayName", ""), team.get("displayName", "?"))
        for inj in team.get("injuries", []):
            name = (inj.get("athlete") or {}).get("displayName")
            if not name:
                continue
            out.append({"name_key": name_key(name), "player": name, "team": code,
                        "status": inj.get("status") or "Unknown",
                        "detail": inj.get("shortComment") or inj.get("longComment") or "",
                        "updated": inj.get("date") or ""})
    return out


def slate(con, day: str):
    """Tonight's games and the players with props on them: {name_key: (player, event_id, matchup, tip)}."""
    rows = con.execute(
        "SELECT DISTINCT p.name_key, p.player, e.event_id, e.away_team, e.home_team, e.commence_time"
        " FROM prop_odds p JOIN events e USING (event_id) WHERE e.game_date=? AND p.label IN ('live','open','bet')",
        (day,))
    return {r[0]: (r[1], r[2], f"{r[3]} @ {r[4]}", r[5]) for r in rows}


def changes(con, feed, day: str):
    """Store the feed; return entries that are news today: a status change, or a new listing dated today."""
    con.executescript(TABLE)
    known = {r[0]: (r[1], r[2]) for r in con.execute("SELECT name_key, status, updated FROM injuries")}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    news = []
    for i in feed:
        before = known.get(i["name_key"])
        dated_today = i["updated"][:10] >= day  # ESPN dates are UTC; evening ET news can carry tomorrow's date
        if before is None:
            if dated_today:
                news.append(i | {"was": None})
        elif before[0] != i["status"]:
            news.append(i | {"was": before[0]})
        con.execute("INSERT OR REPLACE INTO injuries VALUES (?,?,?,?,?,?,?)",
                    (i["name_key"], i["player"], i["team"], i["status"], i["detail"], i["updated"], now))
    listed = {i["name_key"] for i in feed}
    for k, (status, _) in known.items():  # dropped off the report: usually cleared to play
        if k not in listed and status != "Active":
            row = con.execute("SELECT player, team FROM injuries WHERE name_key=?", (k,)).fetchone()
            news.append({"name_key": k, "player": row[0], "team": row[1], "status": "Active",
                         "detail": "No longer on the injury report.", "updated": now, "was": status})
            con.execute("UPDATE injuries SET status='Active', detail=?, updated=?, seen_at=? WHERE name_key=?",
                        ("No longer on the injury report.", now, now, k))
    con.commit()
    return news


def message(con, i, info, day):
    """The alert text: who, what changed, what it means for the card and the board."""
    _, event_id, matchup, tip = info
    tip_et = datetime.fromisoformat(tip.replace("Z", "+00:00")).astimezone(ET).strftime("%I:%M%p").lstrip("0")
    was = f" (was {i['was']})" if i["was"] else ""
    lines = [f"{i['player']}: {i['status']}{was}", f"{matchup} {tip_et} ET. {i['detail']}".strip()]
    on_card = con.execute("SELECT COUNT(*) FROM bets WHERE slate_date=? AND name_key=? AND status IN ('card','locked')",
                          (day, i["name_key"])).fetchone()[0]
    if on_card and i["status"] in ("Out", "Doubtful"):
        lines.append(f"On your card ({on_card} bet{'s' if on_card > 1 else ''}): Hard Rock voids it if they sit.")
    if i["status"] in ("Out", "Doubtful"):
        lines.append("Teammates' props may not have moved yet: check Player out.")
    return lines


def notify(title, body, url):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print(f"[alert] {title}\n        {body}")
        return
    requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), timeout=15,
                  headers={"Title": title.encode("utf-8"), "Tags": "basketball", "Click": url, "Priority": "high"})


def check(con, day: str, refresh_key=None, credits=None, max_credits=60):
    """One pass: fetch, diff, alert on slate players, refresh odds for affected games."""
    tonight = slate(con, day)
    news = [i for i in changes(con, fetch(), day) if i["name_key"] in tonight]
    refreshed = set()
    for i in news:
        info = tonight[i["name_key"]]
        lines = message(con, i, info, day)
        notify(lines[0], "\n".join(lines[1:]), f"{DESK_URL}/#/out")
        event_id = info[1]
        if refresh_key and event_id not in refreshed and credits.used + 5 <= max_credits:
            game = next((e for e in games_on(date.fromisoformat(day), refresh_key, credits) if e["id"] == event_id), None)
            if game and datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00")) > datetime.now(timezone.utc):
                snapshot(con, game, "live", refresh_key, credits)
                refreshed.add(event_id)
                print(f"   refreshed odds for {info[2]} after the news ({credits.used} credits this run)")
    return news


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=str(datetime.now(ET).date()))
    ap.add_argument("--watch", action="store_true", help="check every --every minutes until the last tip")
    ap.add_argument("--every", type=float, default=3)
    ap.add_argument("--no-refresh", action="store_true", help="don't re-pull odds when news hits")
    ap.add_argument("--max-credits", type=int, default=60, help="odds credits this run may spend on refreshes")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    con = connect(a.db) if a.db else connect()
    key = None if a.no_refresh else os.environ.get("ODDS_API_KEY")
    credits = Credits()
    while True:
        news = check(con, a.date, key, credits, a.max_credits)
        print(f"{datetime.now(ET):%I:%M%p} checked: {len(news)} change(s) for tonight's players")
        tips = [r[0] for r in con.execute("SELECT commence_time FROM events WHERE game_date=?", (a.date,))]
        if not a.watch or not tips or max(tips) < datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"):
            break
        time.sleep(a.every * 60)
