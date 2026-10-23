"""Load nflverse schedules/closing lines and team-game EPA into data/nfl.db (free, no credits).

    python -m tipoff.nfl_spreads.load --seasons 2006-2026
    python -m tipoff.nfl_spreads.load --seasons 2026            # refresh the current season
    python -m tipoff.nfl_spreads.load --seasons 2006-2026 --offline   # only use cached files

Sources (downloaded into data/raw/nflverse/, which is gitignored like the rest of data/):
  github.com/nflverse/nfldata  data/games.csv                     schedule, scores, lines, rest, QBs
  github.com/nflverse/nflverse-data releases, tag pbp:
      play_by_play_<season>.csv.gz                                aggregated to team-game EPA

games.csv is re-downloaded on every run (lines and results change in season); a season's
play-by-play is re-downloaded when it is the latest requested season or not yet cached. The load
is idempotent: each season's rows are replaced, then row counts are printed.
"""
import argparse
import csv
import io
from pathlib import Path

import pandas as pd
import requests

from ..leagues import DATA
from .data import PBP_USECOLS, aggregate_pbp, connect_nfl, epa_rows, game_rows

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
CACHE = DATA / "raw" / "nflverse"


def parse_seasons(specs):
    out = set()
    for s in specs:
        for part in str(s).split(","):
            if "-" in part:
                a, b = part.split("-")
                out.update(range(int(a), int(b) + 1))
            elif part:
                out.add(int(part))
    return sorted(out)


def download(url, path: Path, force=False, offline=False):
    if path.exists() and path.stat().st_size > 0 and (offline or not force):
        return path
    if offline:
        return None
    r = requests.get(url, timeout=600)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return path


def load(seasons, db_path=None, cache=CACHE, offline=False):
    con = connect_nfl(db_path)
    gpath = download(GAMES_URL, Path(cache) / "games.csv", force=True, offline=offline)
    if gpath is None:
        raise SystemExit("games.csv is not available (offline and not cached).")
    with open(gpath, encoding="utf-8-sig", newline="") as f:
        grows = game_rows(csv.DictReader(f), set(seasons))
    with con:
        con.execute(f"DELETE FROM nfl_games WHERE season IN ({','.join(map(str, seasons))})")
        con.executemany(f"INSERT OR REPLACE INTO nfl_games VALUES ({','.join('?' * len(grows[0]))})", grows)
    latest = max(seasons)
    for s in seasons:
        p = download(PBP_URL.format(season=s), Path(cache) / "pbp" / f"play_by_play_{s}.csv.gz",
                     force=(s == latest), offline=offline)
        if p is None:
            print(f"[{s}] no play-by-play available; skipped")
            continue
        pbp = pd.read_csv(p, usecols=PBP_USECOLS, low_memory=False)
        rows = epa_rows(aggregate_pbp(pbp))
        with con:
            con.execute("DELETE FROM nfl_team_game_epa WHERE season = ?", (s,))
            if rows:
                con.executemany(f"INSERT INTO nfl_team_game_epa VALUES ({','.join('?' * len(rows[0]))})", rows)
    report(con, seasons)
    con.close()


def report(con, seasons):
    print(f"{'season':>6} {'games':>6} {'final':>6} {'lines':>6} {'team-games EPA':>15} {'games w/o EPA':>14}")
    for s in seasons:
        n, fin, lines = con.execute(
            "SELECT COUNT(*), SUM(result IS NOT NULL), SUM(spread_line IS NOT NULL) FROM nfl_games WHERE season=?",
            (s,)).fetchone()
        e = con.execute("SELECT COUNT(*) FROM nfl_team_game_epa WHERE season=?", (s,)).fetchone()[0]
        miss = con.execute(
            "SELECT COUNT(*) FROM nfl_games g WHERE season=? AND result IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM nfl_team_game_epa e WHERE e.game_id = g.game_id)", (s,)).fetchone()[0]
        print(f"{s:>6} {n:>6} {fin or 0:>6} {lines or 0:>6} {e:>15} {miss:>14}")
    tot = con.execute("SELECT COUNT(*) FROM nfl_games").fetchone()[0]
    tep = con.execute("SELECT COUNT(*) FROM nfl_team_game_epa").fetchone()[0]
    print(f"total: {tot:,} games, {tep:,} team-game EPA rows")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs="+", default=["2006-2026"], help="e.g. 2006-2026 or 2024 2025")
    ap.add_argument("--db", help="database path (default data/nfl.db)")
    ap.add_argument("--offline", action="store_true", help="use cached files only")
    a = ap.parse_args(argv)
    load(parse_seasons(a.seasons), a.db, offline=a.offline)


if __name__ == "__main__":
    main()
