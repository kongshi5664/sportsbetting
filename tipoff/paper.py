"""Paper trading: the agent bets pretend money every night, by the same rules, and learns from it.

    python -m tipoff.paper              # run tonight: decide each game an hour before tip, take closes
    python -m tipoff.paper --once       # decide every game that hasn't started, right now, then stop

For each game, about an hour before tip it:
  1. re-pulls that game's odds (about 5 credits),
  2. records every priced prop at that moment ("marks"), so tomorrow it can see which ones the
     market moved against Hard Rock, bet or not,
  3. places paper bets for each strategy in settings.paper_strategies (each with its own pretend
     bankroll), using exactly the rules the real card uses plus that strategy's overrides,
  4. asks Claude to check the news on the new paper bets (if ANTHROPIC_API_KEY is set).
Five minutes before tip it takes the closing snapshot. The morning box scores grade it all.
Paper bets never touch the real card; the Ledger shows them under Paper.
"""
import argparse
import copy
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .board import price_slate, suggest
from .db import connect
from .features import FeatureStore
from .snapshot import CLOSE_MINUTES, ET, Credits, api_key, games_on, load_env, snapshot

DECIDE_MINUTES = 60
MARKS = """
CREATE TABLE IF NOT EXISTS marks (
    slate_date TEXT NOT NULL,
    market_id  TEXT NOT NULL,     -- event|market|player|point|side
    event_id   TEXT NOT NULL,
    player     TEXT NOT NULL,
    stat       TEXT NOT NULL,
    side       TEXT NOT NULL,
    price      INTEGER NOT NULL,  -- Hard Rock at decision time
    p_market   REAL NOT NULL,     -- market-only fair probability for this side
    p_model    REAL NOT NULL,     -- our projection's probability for this side
    n_refs     INTEGER NOT NULL,
    context    TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    clv        REAL,              -- graded later against the close
    result     TEXT,
    graded     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (slate_date, market_id)
);
"""
DEFAULT_STRATEGIES = [
    {"id": "current", "name": "Today's rules", "overrides": {}},
    {"id": "min3", "name": "3% minimum value", "overrides": {"min_edge": 0.03}},
    {"id": "model15", "name": "Projection back at 15%", "overrides": {"model_weight": 0.15}},
]
START_BANKROLL = 2000


def strategies(cfg):
    return cfg["settings"].get("paper_strategies") or DEFAULT_STRATEGIES


def strategy_cfg(cfg, strat, bankroll):
    """The real rules with this strategy's overrides, sized from its own paper bankroll."""
    c = copy.deepcopy(cfg)
    c["settings"]["bankroll"] = bankroll
    for k, v in strat["overrides"].items():
        rule = next((r for r in c["rules"] if r["id"] == k), None)
        if rule is not None:
            rule.setdefault("params", {})["min"] = v
        else:
            c["settings"][k] = v
    return c


def bankroll(con, strat_id):
    pnl = con.execute("SELECT COALESCE(SUM(CASE WHEN result='win' THEN stake * (CASE WHEN price > 0 THEN price / 100.0"
                      " ELSE 100.0 / -price END) WHEN result='loss' THEN -stake ELSE 0 END), 0) FROM bets"
                      " WHERE paper=1 AND strategy=? AND status='graded'", (strat_id,)).fetchone()[0]
    return round(START_BANKROLL + pnl, 2)


def paper_card(con, day, strat_id):
    return [dict(r) for r in con.execute("SELECT * FROM bets WHERE paper=1 AND strategy=? AND slate_date=?",
                                         (strat_id, day))]


def record_marks(con, games, day):
    """Every priced prop on these games at decision time (both sides), with what it takes to grade it."""
    con.executescript(MARKS)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    for g in games:
        for m in g["all_sides"]:
            con.execute("INSERT OR REPLACE INTO marks (slate_date, market_id, event_id, player, stat, side, price,"
                        " p_market, p_model, n_refs, context, decided_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (day, m["id"], g["event_id"], m["player"], m["stat"], m["side"], m["price"],
                         m["proof"]["p_market"], m["proof"]["p_model"], len(m["proof"]["books"]),
                         json.dumps(m["context"]), now))
            n += 1
    con.commit()
    return n


def decide(con, fs, cfg, day, event_ids):
    """Place tonight's paper bets on these games for every strategy. Returns {strategy: [market]}."""
    placed = {}
    for strat in strategies(cfg):
        scfg = strategy_cfg(cfg, strat, bankroll(con, strat["id"]))
        card = paper_card(con, day, strat["id"])
        games = [g for g in price_slate(con, fs, scfg, day, card=card) if g["event_id"] in event_ids]
        picks = suggest(games, card, scfg)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snaps = {g["event_id"]: g["snapshot_ts"] for g in games}
        for m in picks:
            con.execute(
                "INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair,"
                " edge, stake, snapshot_ts, added_at, status, locked_at, context, paper, strategy)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'locked',?,?,1,?)",
                (day, m["event_id"], m["market"], m["name_key"], m["player"], m["side"], m["point"], m["book"],
                 m["price"], m["fair"], m["edge"], m["stake"], snaps[m["event_id"]], now, now,
                 json.dumps(m["context"]), strat["id"]))
        con.commit()
        placed[strat["id"]] = picks
    return placed


def all_sides(con, fs, cfg, day, event_ids):
    """Both sides of every priced prop (market-only fair price), for the marks table."""
    flat = copy.deepcopy(cfg)
    flat["settings"]["model_weight"] = 0.0
    games = [g for g in price_slate(con, fs, flat, day, card=(), both_sides=True) if g["event_id"] in event_ids]
    for g in games:
        g["all_sides"] = g["markets"]
    return games


def claude_check(con, fs, day, picks):
    """Claude's news check on the night's new paper bets (one call per decision batch)."""
    if not os.environ.get("ANTHROPIC_API_KEY") or not picks:
        return 0
    from . import notes as claude_notes
    legs = {m["id"]: m for m in picks}.values()
    ctx = [claude_notes.leg_context(con, fs, m, day) for m in legs]
    try:
        out = claude_notes.ask_claude(ctx, day)
    except claude_notes.NotesError as e:
        print(f"   Claude check skipped: {e}")
        return 0
    claude_notes.save(con, day, out, {m["id"]: m["price"] for m in legs})
    return len(out)


def run(day, once=False, db=None):
    load_env()
    key = api_key()
    con = connect(db) if db else connect()
    cfg = json.loads((Path(__file__).resolve().parent.parent / "rules.json").read_text(encoding="utf-8"))
    credits = Credits()
    decided, closed = set(), set()
    for (eid,) in con.execute("SELECT DISTINCT event_id FROM bets WHERE paper=1 AND slate_date=?", (str(day),)):
        decided.add(eid)  # restarted mid-evening: don't bet a game twice
    while True:
        now = datetime.now(timezone.utc)
        try:
            games = games_on(day, key, credits)
        except Exception as e:  # network blip: try again next minute
            print(f"{now.astimezone(ET):%I:%M%p} couldn't list games ({e}); retrying")
            time.sleep(60)
            continue
        upcoming = [e for e in games if _tip(e) > now]
        due = [e for e in upcoming if e["id"] not in decided
               and (once or _tip(e) - now <= timedelta(minutes=DECIDE_MINUTES))]
        if due:
            try:
                for e in due:
                    snapshot(con, e, "live", key, credits)
                fs = FeatureStore(con)  # fresh: picks up this morning's box scores
                ids = {e["id"] for e in due}
                sides = all_sides(con, fs, cfg, str(day), ids)
                n_marks = record_marks(con, sides, str(day))
                placed = decide(con, fs, cfg, str(day), ids)
                names = ", ".join(f"{e['away_team']} @ {e['home_team']}" for e in due)
                print(f"{now.astimezone(ET):%I:%M%p} decided {names}: {n_marks} props recorded; "
                      + "; ".join(f"{s}: {len(p)} bets" for s, p in placed.items()))
                checked = claude_check(con, fs, str(day), placed.get("current", []))
                if checked:
                    print(f"   Claude checked {checked} paper bets")
                from . import journal, notes as claude_notes
                best_side = {}
                for g in sides:  # for "passed on", the better side of each prop is enough
                    for m in g["markets"]:
                        k = (m["name_key"], m["market"])
                        if k not in best_side or m["edge"] > best_side[k]["edge"]:
                            best_side[k] = m
                min_edge = next((r["params"]["min"] for r in cfg["rules"] if r["id"] == "min_edge"), 0.02)
                journal.decision_entry(con, str(day), [g for g in sides], placed, list(best_side.values()),
                                       claude_notes.load(con, str(day)), min_edge)
                decided |= ids
            except SystemExit as e:
                print(f"   stopped deciding: {e}")
                return
        for e in upcoming:
            if e["id"] not in closed and _tip(e) - now <= timedelta(minutes=CLOSE_MINUTES):
                try:
                    snapshot(con, e, "close", key, credits)
                    closed.add(e["id"])
                    print(f"{now.astimezone(ET):%I:%M%p} closing prices for {e['away_team']} @ {e['home_team']}")
                except SystemExit as err:
                    print(f"   couldn't take the close: {err}")
        if once or not upcoming:
            print(f"Done for {day}. Credits used: {credits.used}, remaining: {credits.remaining}")
            return
        time.sleep(60)


def _tip(e):
    return datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=date.fromisoformat, default=datetime.now(ET).date())
    ap.add_argument("--once", action="store_true", help="decide every game that hasn't started now, then stop")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    run(a.date, a.once, a.db)
