"""Tables for the NFL spread model, and turning nflverse files into their rows.

nfl_games          one row per game from nflverse's games.csv (schedule, scores, closing lines,
                   rest, weather, starting QBs). Team codes are normalised to today's franchise
                   codes (STL->LA, SD->LAC, OAK->LV) so a franchise's history is continuous;
                   game_id keeps nflverse's original spelling.
nfl_team_game_epa  one row per team per game, aggregated from nflverse play-by-play: offensive
                   and defensive EPA/play (all, pass, rush), success rate and play counts.
                   Raw play-by-play is never stored.

Sign convention: spread_line is the market's expected HOME margin (positive = home favoured);
result = home_score - away_score. Checked on the data: spread_line correlates +0.43 with result
and, when spread_line > 0, the home moneyline is the favourite in 98% of games.
"""
import math

import pandas as pd

from ..db import connect

TEAM_FIX = {"STL": "LA", "SD": "LAC", "OAK": "LV", "JAC": "JAX", "LAR": "LA"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS nfl_games (
    game_id     TEXT PRIMARY KEY,
    season      INTEGER NOT NULL,
    game_type   TEXT NOT NULL,          -- REG, WC, DIV, CON, SB
    week        INTEGER NOT NULL,
    gameday     TEXT NOT NULL,          -- YYYY-MM-DD (US Eastern)
    gametime    TEXT,                   -- HH:MM ET kickoff
    home_team   TEXT NOT NULL,          -- franchise code (LA, LAC, LV for the moved teams)
    away_team   TEXT NOT NULL,
    home_score  INTEGER,
    away_score  INTEGER,
    result      REAL,                   -- home_score - away_score
    location    TEXT,                   -- Home / Neutral
    spread_line REAL,                   -- market's expected HOME margin (+ = home favoured)
    total_line  REAL,
    home_moneyline INTEGER, away_moneyline INTEGER,
    home_spread_odds INTEGER, away_spread_odds INTEGER,
    home_rest   INTEGER, away_rest INTEGER,
    div_game    INTEGER,
    roof TEXT, surface TEXT, temp REAL, wind REAL,
    home_qb_id TEXT, away_qb_id TEXT, home_qb_name TEXT, away_qb_name TEXT
);
CREATE INDEX IF NOT EXISTS ix_nflg_season ON nfl_games(season, gameday);

CREATE TABLE IF NOT EXISTS nfl_team_game_epa (
    game_id   TEXT NOT NULL,
    team      TEXT NOT NULL,
    season    INTEGER NOT NULL,
    week      INTEGER NOT NULL,
    opponent  TEXT NOT NULL,
    off_plays INTEGER, off_epa REAL, off_success REAL,
    off_pass_plays INTEGER, off_pass_epa REAL, off_rush_plays INTEGER, off_rush_epa REAL,
    def_plays INTEGER, def_epa REAL, def_success REAL,
    def_pass_plays INTEGER, def_pass_epa REAL, def_rush_plays INTEGER, def_rush_epa REAL,
    PRIMARY KEY (game_id, team)
);
"""

GAME_COLS = ("game_id", "season", "game_type", "week", "gameday", "gametime", "home_team", "away_team",
             "home_score", "away_score", "result", "location", "spread_line", "total_line",
             "home_moneyline", "away_moneyline", "home_spread_odds", "away_spread_odds",
             "home_rest", "away_rest", "div_game", "roof", "surface", "temp", "wind",
             "home_qb_id", "away_qb_id", "home_qb_name", "away_qb_name")
INT_COLS = {"season", "week", "home_score", "away_score", "home_moneyline", "away_moneyline",
            "home_spread_odds", "away_spread_odds", "home_rest", "away_rest", "div_game"}
REAL_COLS = {"result", "spread_line", "total_line", "temp", "wind"}

EPA_COLS = ("game_id", "team", "season", "week", "opponent",
            "off_plays", "off_epa", "off_success", "off_pass_plays", "off_pass_epa", "off_rush_plays", "off_rush_epa",
            "def_plays", "def_epa", "def_success", "def_pass_plays", "def_pass_epa", "def_rush_plays", "def_rush_epa")
PBP_USECOLS = ["game_id", "season", "week", "posteam", "defteam", "play_type", "epa", "success", "pass"]


def connect_nfl(path=None, **kwargs):
    """data/nfl.db (or `path`) with the league's usual tables plus the spread-model tables."""
    con = connect(path, league="nfl", **kwargs)
    con.executescript(SCHEMA)
    return con


def team(code):
    return TEAM_FIX.get(code, code)


def _blank(v):
    return v is None or v == "" or (isinstance(v, float) and math.isnan(v))


def _num(v, kind):
    if _blank(v):
        return None
    try:
        return int(round(float(v))) if kind is int else float(v)
    except (TypeError, ValueError):
        return None


def game_rows(rows, seasons=None):
    """games.csv dicts -> nfl_games tuples (optionally only some seasons)."""
    out = []
    for g in rows:
        season = _num(g.get("season"), int)
        if season is None or (seasons is not None and season not in seasons):
            continue
        rec = []
        for c in GAME_COLS:
            v = g.get(c)
            if c in INT_COLS:
                v = _num(v, int)
            elif c in REAL_COLS:
                v = _num(v, float)
            elif c in ("home_team", "away_team"):
                v = team(v)
            else:
                v = None if _blank(v) else str(v)
            rec.append(v)
        out.append(tuple(rec))
    return out


def aggregate_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    """Play-by-play -> one row per team per game (offence and defence).

    Plays counted: play_type 'pass' or 'run' with an EPA (scrambles and sacks are dropbacks, so
    `pass` == 1 splits pass from rush). Kneels, spikes, special teams and no-plays are left out.
    """
    p = pbp[pbp["play_type"].isin(["pass", "run"]) & pbp["epa"].notna() & pbp["posteam"].notna()].copy()
    p["posteam"] = p["posteam"].map(team)
    p["defteam"] = p["defteam"].map(team)
    p["is_pass"] = (p["pass"].fillna(0) == 1)
    p["success"] = p["success"].fillna(0)
    p["pass_epa"] = p["epa"].where(p["is_pass"])
    p["rush_epa"] = p["epa"].where(~p["is_pass"])
    g = p.groupby(["game_id", "posteam"]).agg(
        season=("season", "first"), week=("week", "first"), opponent=("defteam", "first"),
        plays=("epa", "size"), epa=("epa", "mean"), success=("success", "mean"),
        pass_plays=("is_pass", "sum"), pass_epa=("pass_epa", "mean"),
        rush_epa=("rush_epa", "mean")).reset_index().rename(columns={"posteam": "team"})
    g["rush_plays"] = g["plays"] - g["pass_plays"]
    stats = ["plays", "epa", "success", "pass_plays", "pass_epa", "rush_plays", "rush_epa"]
    off = g.rename(columns={s: f"off_{s}" for s in stats})
    dfn = g[["game_id", "team", *stats]].rename(columns={"team": "opponent", **{s: f"def_{s}" for s in stats}})
    out = off.merge(dfn, on=["game_id", "opponent"], how="left")
    for c in ("off_plays", "off_pass_plays", "off_rush_plays", "def_plays", "def_pass_plays", "def_rush_plays"):
        out[c] = out[c].fillna(0).astype(int)
    return out[list(EPA_COLS)]


def epa_rows(agg: pd.DataFrame):
    """Aggregated frame -> plain Python tuples for sqlite (NaN -> NULL, numpy scalars -> Python)."""
    def py(v):
        if hasattr(v, "item"):
            v = v.item()
        return None if isinstance(v, float) and math.isnan(v) else v
    return [tuple(py(v) for v in r) for r in agg[list(EPA_COLS)].itertuples(index=False)]


def load_games(con, seasons=None) -> pd.DataFrame:
    q = "SELECT * FROM nfl_games"
    if seasons:
        q += f" WHERE season IN ({','.join(str(int(s)) for s in seasons)})"
    return pd.read_sql_query(q + " ORDER BY gameday, gametime, game_id", con)


def load_epa(con) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM nfl_team_game_epa", con)
