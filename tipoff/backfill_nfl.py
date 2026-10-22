"""Backfill NFL box scores from nflverse's free weekly CSVs (no key, no credits).

    python -m tipoff.backfill_stats --league nfl --seasons 2023 2024 2025 2026

Sources (github.com/nflverse/nflverse-data releases):
  stats_player/stats_player_week_<season>.csv   one row per player per game (REG and POST)
  stats_team/stats_team_week_<season>.csv       one row per team per game (for the matchup factor)
  schedules/games.csv                           game day (US Eastern), home/away teams, scores

nflverse rebuilds the current season's files from play-by-play during the season, usually
within a day of the games, so grading lags until then. Only offensive players are kept
(QB/RB/FB/WR/TE, plus anyone with a pass attempt, carry or target). Rows are upserted.
"""
import csv
import io
from collections import defaultdict

import requests

from .db import connect, name_key

RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
PLAYERS = RELEASES + "/stats_player/stats_player_week_{season}.csv"
TEAMS = RELEASES + "/stats_team/stats_team_week_{season}.csv"
GAMES = RELEASES + "/schedules/games.csv"
OFFENSE = {"QB", "RB", "FB", "WR", "TE"}
# nflverse column -> our stat column
PLAYER_COLS = {"passing_yards": "pass_yds", "attempts": "pass_att", "completions": "pass_cmp",
               "rushing_yards": "rush_yds", "carries": "rush_att", "receiving_yards": "rec_yds",
               "receptions": "rec", "targets": "targets"}
TEAM_COLS = {"passing_yards": "pass_yds", "attempts": "pass_att", "rushing_yards": "rush_yds",
             "carries": "rush_att", "receiving_yards": "rec_yds", "receptions": "rec"}


def fetch_csv(url):
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        return None  # that season isn't published (yet)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))


def _int(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def schedule(rows):
    """games.csv rows -> {game_id: {date, home, away, home_score, away_score}}."""
    return {g["game_id"]: {"date": g["gameday"], "home": g["home_team"], "away": g["away_team"],
                           "home_score": _int(g.get("home_score")), "away_score": _int(g.get("away_score"))}
            for g in rows}


def player_rows(rows, games, season):
    """nflverse weekly player stats -> player_games tuples, plus the rows that couldn't be placed
    (no schedule match) so they are reported rather than silently dropped."""
    out, unplaced = [], []
    for r in rows:
        pos = r.get("position") or ""
        involved = any((_int(r.get(c)) or 0) > 0 for c in ("attempts", "carries", "targets"))
        if pos not in OFFENSE and not involved:
            continue
        g = games.get(r["game_id"])
        if g is None:
            unplaced.append(r)
            continue
        name = r.get("player_display_name") or r.get("player_name")
        team = r["team"]
        out.append((str(season), r["game_id"], g["date"], r["player_id"], name, name_key(name), team,
                    r["opponent_team"], int(team == g["home"]), None, pos,
                    *[_int(r.get(c)) for c in PLAYER_COLS]))
    return out, unplaced


def team_rows(rows, games, season):
    out = []
    for r in rows:
        g = games.get(r["game_id"])
        if g is None:
            continue
        home = r["team"] == g["home"]
        pts, opp_pts = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
        out.append((str(season), r["game_id"], g["date"], r["team"], r["opponent_team"], int(home), pts, opp_pts,
                    *[_int(r.get(c)) for c in TEAM_COLS]))
    return out


def name_collisions(rows):
    """Different players who share a name key in one season. Odds feeds name players only by name,
    so these would mix two players' games: log them so they can be fixed."""
    ids = defaultdict(set)
    names = {}
    for r in rows:
        ids[r[5]].add(r[3])
        names[(r[5], r[3])] = f"{r[4]} ({r[10]}, {r[6]})"
    return {k: sorted(names[(k, i)] for i in v) for k, v in ids.items() if len(v) > 1}


def backfill(seasons, db_path=None, fetch=fetch_csv):
    con = connect(db_path, league="nfl")
    games = schedule(fetch(GAMES) or [])
    summary = []
    for season in seasons:
        season = str(season)
        prows = fetch(PLAYERS.format(season=season))
        if prows is None:
            print(f"[{season}] nflverse has no weekly player stats for this season yet; skipped")
            continue
        rows, unplaced = player_rows(prows, games, season)
        if rows:
            con.executemany(f"INSERT OR REPLACE INTO player_games VALUES ({','.join('?' * len(rows[0]))})", rows)
        weeks = sorted({_int(r.get("week")) for r in prows if r.get("week")} - {None})
        print(f"[{season}] {len(rows):,} player-games (weeks {weeks[0]}-{weeks[-1]})" if weeks else
              f"[{season}] {len(rows):,} player-games")
        if unplaced:
            ids = sorted({r["game_id"] for r in unplaced})
            print(f"   ! {len(unplaced)} rows in {len(ids)} games have no schedule match: {', '.join(ids[:6])}")
        for k, who in sorted(name_collisions(rows).items()):
            print(f"   ! name key '{k}' is shared by: {'; '.join(who)}")
        trows = team_rows(fetch(TEAMS.format(season=season)) or [], games, season)
        if trows:
            con.executemany(f"INSERT OR REPLACE INTO team_games VALUES ({','.join('?' * len(trows[0]))})", trows)
        con.commit()
        print(f"   {len(trows):,} team-games")
        summary.append((season, len(rows), len(trows)))
    con.close()
    return summary
