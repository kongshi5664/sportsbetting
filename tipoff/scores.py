"""Live scores and box scores during the games, so open bets can be followed as they play out.

Source: ESPN's public scoreboard and game summary (no key, no credits). Only for watching:
grading still uses the official box scores loaded the next morning.
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from .db import name_key

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_TO_NBA = {"WSH": "WAS", "GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA"}
STAT_KEYS = {"pts": "points", "reb": "rebounds", "ast": "assists", "blk": "blocks",
             "fg3m": "threePointFieldGoalsMade-threePointFieldGoalsAttempted"}
TTL = 30  # seconds; the feed itself updates about this often
_cache = {}


def _get(path, params):
    key = (path, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    data = requests.get(f"{BASE}/{path}", params=params, timeout=15).json()
    _cache[key] = (time.monotonic(), data)
    return data


def code(abbr):
    return ESPN_TO_NBA.get(abbr, abbr)


def elapsed(period, clock):
    """Game minutes played, from the period and the clock ('7:42' or '12.3')."""
    if not period:
        return 0.0
    if ":" in clock:
        m, s = clock.split(":")
        left = int(m) + float(s) / 60
    else:
        left = float(clock or 0) / 60
    length = 12 if period <= 4 else 5
    before = min(period - 1, 4) * 12 + max(0, period - 5) * 5
    return before + max(0.0, length - left)


def games(day):
    """Every game on an ET date: teams as NBA codes, scores, and where the game is."""
    data = _get("scoreboard", {"dates": day.replace("-", "")})
    out = []
    for e in data.get("events", []):
        c = e["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        st = e["status"]
        out.append({
            "espn_id": e["id"], "away": code(teams["away"]["team"]["abbreviation"]),
            "home": code(teams["home"]["team"]["abbreviation"]),
            "away_score": int(teams["away"].get("score") or 0), "home_score": int(teams["home"].get("score") or 0),
            "state": st["type"]["state"],  # pre / in / post
            "period": st.get("period") or 0, "clock": st.get("displayClock") or "",
            "detail": st["type"].get("shortDetail") or "",
            "elapsed": 48.0 if st["type"]["state"] == "post" else elapsed(st.get("period"), st.get("displayClock") or ""),
        })
    return out


def box(espn_id):
    """{name_key: {stat: value, 'min': minutes, 'dnp': bool}} for one game so far."""
    data = _get("summary", {"event": espn_id})
    out = {}
    for team in data.get("boxscore", {}).get("players", []):
        for block in team.get("statistics", []):
            keys = block.get("keys", [])
            for a in block.get("athletes", []):
                row = dict(zip(keys, a.get("stats", [])))
                p = {"dnp": bool(a.get("didNotPlay")), "min": _num(row.get("minutes"))}
                for stat, k in STAT_KEYS.items():
                    p[stat] = _num(row.get(k, "").split("-")[0])
                out[name_key(a["athlete"]["displayName"])] = p
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def track(day, bets):
    """Live progress for each open bet (dicts with id, home, away, name_key, stat, side, point).
    A bet's status: 'pre' before tip; 'hit'/'dead' once settled in-game (an over that cleared its line,
    an under that went past it); otherwise 'live' with the pace the player is on."""
    try:
        gs = games(day)
    except Exception:
        return {"games": [], "bets": {}}
    by_teams = {(g["away"], g["home"]): g for g in gs}
    boxes, out = {}, {}
    for b in bets:
        g = by_teams.get((b["away"], b["home"]))
        if not g:
            continue
        row = {"state": g["state"], "detail": g["detail"]}
        if g["state"] != "pre":
            if g["espn_id"] not in boxes:
                try:
                    boxes[g["espn_id"]] = box(g["espn_id"])
                except Exception:
                    boxes[g["espn_id"]] = {}
            p = boxes[g["espn_id"]].get(b["name_key"])
            if p:
                now = p[b["stat"]]
                pace = now * 48 / g["elapsed"] if g["elapsed"] >= 6 else None
                over = b["side"] == "Over"
                if g["state"] == "post":
                    status = "void" if p["dnp"] or not p["min"] else (
                        "won" if (now > b["point"]) == over and now != b["point"] else "lost")
                elif over and now > b["point"]:
                    status = "won"
                elif not over and now > b["point"]:
                    status = "lost"
                else:
                    status = "live"
                row.update(now=now, min=p["min"], pace=None if pace is None else round(pace, 1),
                           on_pace=None if pace is None else (pace > b["point"]) == over, status=status)
        out[str(b["id"])] = row
    return {"games": gs, "bets": out}
