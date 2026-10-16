"""Backfill NBA box scores with the free nba_api package.

    python -m tipoff.backfill_stats --seasons 2023-24 2024-25 2025-26

Takes a few minutes per season. stats.nba.com throttles fast clients, so the script
pauses between calls. Safe to re-run: rows are upserted.
"""
import argparse
import time

from .db import connect, name_key

STAT_COLS = {"PTS": "pts", "REB": "reb", "AST": "ast", "BLK": "blk", "STL": "stl", "FG3M": "fg3m", "TOV": "tov"}


def _parse_matchup(matchup: str):
    # "BOS vs. DET" -> home game vs DET ; "BOS @ DET" -> away game at DET
    if " vs. " in matchup:
        team, opp = matchup.split(" vs. ")
        return team.strip(), opp.strip(), 1
    team, opp = matchup.split(" @ ")
    return team.strip(), opp.strip(), 0


def _minutes(v):
    if v is None:
        return None
    if isinstance(v, str) and ":" in v:
        m, s = v.split(":")
        return int(m) + int(s) / 60
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch(season: str, kind: str):
    from nba_api.stats.endpoints import leaguegamelog
    log = leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star="Regular Season",
        player_or_team_abbreviation=kind,  # "P" players, "T" teams
        timeout=60,
    )
    return log.get_data_frames()[0]


def backfill(seasons, db_path=None):
    con = connect(db_path) if db_path else connect()
    for season in seasons:
        print(f"[{season}] player logs...")
        df = fetch(season, "P")
        rows = []
        for r in df.to_dict("records"):
            team, opp, home = _parse_matchup(r["MATCHUP"])
            rows.append((
                season, r["GAME_ID"], str(r["GAME_DATE"])[:10], int(r["PLAYER_ID"]), r["PLAYER_NAME"],
                name_key(r["PLAYER_NAME"]), team, opp, home, _minutes(r.get("MIN")),
                *[r.get(c) for c in STAT_COLS],
            ))
        con.executemany(
            "INSERT OR REPLACE INTO player_games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        print(f"  {len(rows):,} player-games")
        time.sleep(2)

        print(f"[{season}] team logs...")
        tdf = fetch(season, "T")
        pts_by = {(r["GAME_ID"], r["TEAM_ABBREVIATION"]): r["PTS"] for r in tdf.to_dict("records")}
        trows = []
        for r in tdf.to_dict("records"):
            team, opp, home = _parse_matchup(r["MATCHUP"])
            trows.append((season, r["GAME_ID"], str(r["GAME_DATE"])[:10], team, opp, home,
                          r["PTS"], pts_by.get((r["GAME_ID"], opp)), r["REB"], r["AST"]))
        con.executemany("INSERT OR REPLACE INTO team_games VALUES (?,?,?,?,?,?,?,?,?,?)", trows)
        con.commit()
        print(f"  {len(trows):,} team-games")
        time.sleep(2)
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", required=True, help="e.g. 2024-25 2025-26")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    backfill(a.seasons, a.db)
