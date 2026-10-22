"""SQLite storage shared by the backfills, the backtest and (later) the live app."""
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "tipoff.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_games (
    season      TEXT NOT NULL,
    game_id     TEXT NOT NULL,
    game_date   TEXT NOT NULL,          -- YYYY-MM-DD, US Eastern
    player_id   INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    name_key    TEXT NOT NULL,          -- normalized name for matching odds
    team        TEXT NOT NULL,
    opponent    TEXT NOT NULL,
    home        INTEGER NOT NULL,
    minutes     REAL,
    pts INTEGER, reb INTEGER, ast INTEGER, blk INTEGER, stl INTEGER, fg3m INTEGER, tov INTEGER,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_pg_name_date ON player_games(name_key, game_date);

CREATE TABLE IF NOT EXISTS team_games (
    season    TEXT NOT NULL,
    game_id   TEXT NOT NULL,
    game_date TEXT NOT NULL,
    team      TEXT NOT NULL,
    opponent  TEXT NOT NULL,
    home      INTEGER NOT NULL,
    pts INTEGER, opp_pts INTEGER, reb INTEGER, ast INTEGER,
    PRIMARY KEY (game_id, team)
);
CREATE INDEX IF NOT EXISTS ix_tg_team_date ON team_games(team, game_date);

CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    commence_time TEXT NOT NULL,        -- ISO UTC
    game_date     TEXT NOT NULL,        -- US Eastern date
    home_team     TEXT NOT NULL,
    away_team     TEXT NOT NULL
);

-- One row per outcome price seen in one snapshot.
-- label: 'bet' = the moment you'd have placed the bet, 'close' = just before tip.
CREATE TABLE IF NOT EXISTS prop_odds (
    event_id    TEXT NOT NULL,
    label       TEXT NOT NULL,
    snapshot_ts TEXT NOT NULL,
    book        TEXT NOT NULL,
    market      TEXT NOT NULL,          -- player_points, player_rebounds, ...
    player      TEXT NOT NULL,
    name_key    TEXT NOT NULL,
    side        TEXT NOT NULL,          -- Over / Under
    point       REAL NOT NULL,
    price       INTEGER NOT NULL,       -- American odds
    PRIMARY KEY (event_id, label, book, market, name_key, side, point)
);
CREATE INDEX IF NOT EXISTS ix_po_event ON prop_odds(event_id, label);

-- Real bets from the live desk. status: 'card' (on tonight's card), 'locked', 'graded'.
-- Every bet keeps the price taken and, once graded, the closing price (CLV is the scoreboard).
CREATE TABLE IF NOT EXISTS bets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slate_date  TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    market      TEXT NOT NULL,
    name_key    TEXT NOT NULL,
    player      TEXT NOT NULL,
    side        TEXT NOT NULL,
    point       REAL NOT NULL,
    book        TEXT NOT NULL,
    price       INTEGER NOT NULL,       -- American odds taken
    fair        REAL NOT NULL,          -- fair win probability when added
    edge        REAL NOT NULL,
    stake       REAL NOT NULL,
    snapshot_ts TEXT,
    added_at    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'card',
    locked_at   TEXT,
    placed      INTEGER NOT NULL DEFAULT 0,
    close_price INTEGER,
    clv         REAL,
    result      TEXT,                   -- win / loss / push / void
    actual      REAL,
    context     TEXT,                   -- JSON snapshot at add time, read by the weekly review
    paper       INTEGER NOT NULL DEFAULT 0,  -- 1 = placed by the paper trader, never real money
    strategy    TEXT                    -- which paper strategy made it (null for real bets)
);
CREATE INDEX IF NOT EXISTS ix_bets_date ON bets(slate_date, status);
"""


def connect(path=DEFAULT_DB, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, **kwargs)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(bets)")}
    if "context" not in cols:  # what was true when the bet was taken: features, prices, rules matched
        con.execute("ALTER TABLE bets ADD COLUMN context TEXT")
    if "paper" not in cols:  # paper-trading bets from tipoff.paper, kept apart from the real card
        con.execute("ALTER TABLE bets ADD COLUMN paper INTEGER NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE bets ADD COLUMN strategy TEXT")
    return con


def name_key(name: str) -> str:
    """'Shai Gilgeous-Alexander Jr.' -> 'shaigilgeousalexander'. Odds feeds and the NBA
    stats API spell names differently; this makes them match in almost all cases."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    for suffix in (" jr.", " jr", " sr.", " sr", " iii", " ii", " iv"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return "".join(ch for ch in s if ch.isalpha())
