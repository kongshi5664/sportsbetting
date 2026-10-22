"""Claude's notes on tonight's bets: news and context the price may not reflect yet.

Claude reads each candidate leg (our numbers plus the player's recent games), searches the web
for injury and lineup news, and returns a verdict per leg: "clear", "caution" or "skip", with a
one-line reason. Notes are advice shown next to the bet. They never add a bet, never change a
price or a stake, and never override a rule; the rulebook and the price still decide.

    python -m tipoff.notes --date 2026-10-20 --db data/tipoff.db
"""
import argparse
import json
import os
from datetime import datetime, timezone

import anthropic

from .features import MARKET_STAT
from .snapshot import load_env

MODEL = "claude-opus-5-5"
VERDICTS = ("clear", "caution", "skip")

SYSTEM = """You are the analyst on a two-person sports-betting desk. The desk only bets when a \
sportsbook's price beats a fair price taken from the rest of the market; that edge is already \
computed and is not your call. Your job is to catch what the price may not reflect yet.

For each leg you are given, search for current news (injury reports, questionable or out \
designations, minutes restrictions, rest days, lineup or role changes, coaching comments) about \
the player and their team for this game. Then give one verdict per leg:
- "clear": nothing found that undercuts the bet.
- "caution": something worth a second look before placing it (questionable tag, possible \
minutes cap, role change, conflicting reports, or the bet leans on a stale line).
- "skip": concrete news that the bet's premise is gone (player ruled out or very likely out, \
confirmed minutes restriction, a teammate's return that clearly cuts this player's role).

Write each note in plain words a bettor would use, at most 25 words, naming the specific fact \
and its source when you have one. If you found nothing, say so plainly and mark it "clear". Do \
not invent news, do not judge the price or the edge, and do not suggest other bets."""

SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "note": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "verdict", "note", "sources"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["notes"],
    "additionalProperties": False,
}

NOTES_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
    slate_date TEXT NOT NULL,
    market_id  TEXT NOT NULL,     -- the board's market id (event|market|player|point|side)
    verdict    TEXT NOT NULL,     -- clear / caution / skip
    note       TEXT NOT NULL,
    sources    TEXT NOT NULL,     -- JSON list of URLs
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    price      INTEGER,           -- Hard Rock price when Claude judged it
    clv        REAL,              -- graded later against the close, bet or not
    graded     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (slate_date, market_id)
);
"""


def ensure_table(con):
    con.executescript(NOTES_TABLE)
    cols = {r[1] for r in con.execute("PRAGMA table_info(notes)")}
    for col, decl in (("price", "INTEGER"), ("clv", "REAL"), ("graded", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:
            con.execute(f"ALTER TABLE notes ADD COLUMN {col} {decl}")


class NotesError(Exception):
    """Something the user can act on (no key, refusal, bad response)."""


def leg_context(con, fs, m, date):
    """What Claude reads for one leg: our numbers and the player's recent games before tonight."""
    stat = MARKET_STAT[m["market"]]
    rows = [g for g in fs.by_player.get(m["name_key"], []) if g["game_date"] < date][-10:]
    return {
        "id": m["id"], "player": m["player"], "team": m["team"], "game": m["matchup"],
        "tip": m["commence_time"], "market": m["stat_label"], "pick": f"{m['side']} {m['point']:g}",
        "hard_rock": m["price"], "fair": m["fair_american"], "edge": round(m["edge"], 4),
        "projection": m["proof"]["projection"],
        "last_games": [{"date": g["game_date"], "vs": g["opponent"], "min": g["minutes"], stat: g[stat]}
                       for g in rows],
    }


def ask_claude(legs, date, league="NBA"):
    """One request: web search for news, structured verdicts back. Returns {market_id: note}."""
    load_env()
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise NotesError("No Claude API key yet. Add ANTHROPIC_API_KEY to .env (console.anthropic.com) "
                         "and restart the server.")
    client = anthropic.Anthropic()
    prompt = (f"League: {league}. Slate date: {date} (US Eastern). Today's UTC time: "
              f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}.\n\nLegs:\n{json.dumps(legs, indent=1)}")
    messages = [{"role": "user", "content": prompt}]
    params = dict(
        model=MODEL, max_tokens=16000, system=SYSTEM,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        # If a safety classifier declines, the API retries on a fallback model in the same call.
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    try:
        resp = client.beta.messages.create(messages=messages, **params)
        for _ in range(5):  # web search can pause a long turn; resend to let it resume
            if resp.stop_reason != "pause_turn":
                break
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
            resp = client.beta.messages.create(messages=messages, **params)
    except anthropic.AuthenticationError:
        raise NotesError("Claude rejected the API key. Set ANTHROPIC_API_KEY in .env and restart the server.")
    except anthropic.RateLimitError:
        raise NotesError("Claude is rate-limited right now. Try again in a minute.")
    except anthropic.APIStatusError as e:
        raise NotesError(f"Claude's API returned {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise NotesError("Couldn't reach Claude's API. Check the connection and try again.")
    if resp.stop_reason == "refusal":
        raise NotesError("Claude declined this request, so there are no notes tonight. The bets are unaffected.")
    if resp.stop_reason == "max_tokens":
        raise NotesError("Claude's answer was cut off. Try again with fewer legs.")
    text = next((b.text for b in reversed(resp.content) if b.type == "text"), None)
    if not text:
        raise NotesError("Claude returned no notes. Try again.")
    ids = {l["id"] for l in legs}
    return {n["id"]: n for n in json.loads(text)["notes"] if n["id"] in ids and n["verdict"] in VERDICTS}


def save(con, date, notes, prices=None):
    """prices: {market_id: Hard Rock price Claude saw}, so each call can be graded later."""
    ensure_table(con)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.executemany("INSERT OR REPLACE INTO notes (slate_date, market_id, verdict, note, sources, model, created_at,"
                    " price, clv, graded) VALUES (?,?,?,?,?,?,?,?,NULL,0)",
                    [(date, mid, n["verdict"], n["note"], json.dumps(n["sources"]), MODEL, now,
                      (prices or {}).get(mid)) for mid, n in notes.items()])
    con.commit()


def load(con, date):
    ensure_table(con)
    return {r["market_id"]: {"verdict": r["verdict"], "note": r["note"], "sources": json.loads(r["sources"]),
                             "created_at": r["created_at"]}
            for r in con.execute("SELECT * FROM notes WHERE slate_date=?", (date,))}


if __name__ == "__main__":
    from .api import _candidates
    from .db import DEFAULT_DB

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    a = ap.parse_args()
    os.environ["TIPOFF_DB"] = a.db
    from . import api

    api.DB_PATH = api.Path(a.db)
    legs = _candidates(a.date)
    notes = ask_claude([leg_context(api.con(), api.features(), m, a.date) for m in legs], a.date)
    save(api.con(), a.date, notes, {m["id"]: m["price"] for m in legs})
    for m in legs:
        n = notes.get(m["id"])
        print(f"{m['player']} {m['stat_label']} {m['side'][0]} {m['point']:g}: "
              + (f"[{n['verdict']}] {n['note']}" if n else "(no note)"))
