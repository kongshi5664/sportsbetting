"""Live scores and box scores during the games, so open bets can be followed as they play out.

Source: ESPN's public scoreboard and game summary (no key, no credits), per league
(basketball/nba, football/nfl). Only for watching: grading still uses the official box scores
loaded the next morning.
"""
import time

import requests

from . import leagues
from .db import name_key
from .leagues import NBA

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_TO_NBA = NBA.espn_codes
STAT_KEYS = {"pts": "points", "reb": "rebounds", "ast": "assists", "blk": "blocks",
             "fg3m": "threePointFieldGoalsMade-threePointFieldGoalsAttempted"}
# Football box scores come in categories, and a player can appear in several (a QB passes and
# runs). stat -> (category, ESPN key, which part of an "a/b" value).
NFL_STAT_KEYS = {"pass_yds": ("passing", "passingYards", 0), "pass_att": ("passing", "completions/passingAttempts", 1),
                 "rush_yds": ("rushing", "rushingYards", 0), "rush_att": ("rushing", "rushingAttempts", 0),
                 "rec_yds": ("receiving", "receivingYards", 0), "rec": ("receiving", "receptions", 0)}
TTL = 30  # seconds; the feed itself updates about this often
_cache = {}


def _base(league=None):
    return f"https://site.api.espn.com/apis/site/v2/sports/{leagues.get(league).espn_path}"


def _get(path, params, league=None):
    url = f"{_base(league)}/{path}"
    key = (url, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    data = requests.get(url, params=params, timeout=15).json()
    _cache[key] = (time.monotonic(), data)
    return data


def code(abbr, league=None):
    return leagues.get(league).espn_codes.get(abbr, abbr)


def elapsed(period, clock, league=None):
    """Game minutes played, from the period and the clock ('7:42' or '12.3')."""
    lg = leagues.get(league)
    if not period:
        return 0.0
    if ":" in clock:
        m, s = clock.split(":")
        left = int(m) + float(s) / 60
    else:
        left = float(clock or 0) / 60
    n, q, ot = lg.periods, lg.period_minutes, lg.ot_minutes
    length = q if period <= n else ot
    before = min(period - 1, n) * q + max(0, period - n - 1) * ot
    return before + max(0.0, length - left)


def games(day, league=None):
    """Every game on an ET date: teams as box-score codes, scores, and where the game is."""
    lg = leagues.get(league)
    data = _get("scoreboard", {"dates": day.replace("-", "")}, lg)
    out = []
    for e in data.get("events", []):
        c = e["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        st = e["status"]
        out.append({
            "espn_id": e["id"], "away": code(teams["away"]["team"]["abbreviation"], lg),
            "home": code(teams["home"]["team"]["abbreviation"], lg),
            "away_score": int(teams["away"].get("score") or 0), "home_score": int(teams["home"].get("score") or 0),
            "state": st["type"]["state"],  # pre / in / post
            "period": st.get("period") or 0, "clock": st.get("displayClock") or "",
            "detail": st["type"].get("shortDetail") or "",
            "elapsed": float(lg.game_minutes) if st["type"]["state"] == "post"
            else elapsed(st.get("period"), st.get("displayClock") or "", lg),
        })
    return out


def box(espn_id, league=None):
    """{name_key: {stat: value, 'min': minutes, 'dnp': bool}} for one game so far.
    Leagues without minutes (NFL) report 'min' as None; a listed player has played."""
    lg = leagues.get(league)
    data = _get("summary", {"event": espn_id}, lg)
    if lg.id != "nba":
        return _football_box(data, lg)
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


def _football_box(data, lg):
    out = {}
    for team in data.get("boxscore", {}).get("players", []):
        for block in team.get("statistics", []):
            keys = block.get("keys", [])
            for a in block.get("athletes", []):
                row = dict(zip(keys, a.get("stats", [])))
                p = out.setdefault(name_key(a["athlete"]["displayName"]),
                                   {"dnp": False, "min": None, **{s: 0.0 for s in lg.market_stat.values()}})
                p["dnp"] = p["dnp"] or bool(a.get("didNotPlay"))
                for stat, (cat, k, part) in NFL_STAT_KEYS.items():
                    if block.get("name") == cat and k in row:
                        parts = str(row[k]).split("/")
                        p[stat] = _num(parts[part] if part < len(parts) else None)
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def track(day, bets, league=None):
    """Live progress for each open bet (dicts with id, home, away, name_key, stat, side, point).
    A bet's status: 'pre' before kickoff; 'hit'/'dead' once settled in-game (an over that cleared its
    line, an under that went past it); otherwise 'live' with the pace the player is on."""
    lg = leagues.get(league)
    try:
        gs = games(day, lg)
    except Exception:
        return {"games": [], "bets": {}}
    by_teams = {(g["away"], g["home"]): g for g in gs}
    boxes, out = {}, {}
    full = lg.game_minutes
    for b in bets:
        g = by_teams.get((b["away"], b["home"]))
        if not g:
            continue
        row = {"state": g["state"], "detail": g["detail"]}
        if g["state"] != "pre":
            if g["espn_id"] not in boxes:
                try:
                    boxes[g["espn_id"]] = box(g["espn_id"], lg)
                except Exception:
                    boxes[g["espn_id"]] = {}
            p = boxes[g["espn_id"]].get(b["name_key"])
            if p:
                now = p[b["stat"]]
                pace = now * full / g["elapsed"] if g["elapsed"] >= full / 8 else None
                over = b["side"] == "Over"
                if g["state"] == "post":
                    sat = p["dnp"] or (lg.has_minutes and not p["min"])
                    status = "void" if sat else ("won" if (now > b["point"]) == over and now != b["point"] else "lost")
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
