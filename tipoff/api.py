"""Small FastAPI server for the live desk. Reads the SQLite DB and rules.json; never places bets.

    python -m tipoff.api --db data/sample.db      # http://127.0.0.1:8000 (serves web/dist if built)
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from .backtest import ROOT, _load_snapshot, metrics
from .board import STAT_LABEL, price_slate, rule_params, slate_dates, suggest
from .db import DEFAULT_DB, connect
from .features import MARKET_STAT, FeatureStore
from .pricing import consensus, ev, to_american
from . import grading
from . import injuries as injury_feed
from . import notes as claude_notes
from . import review as weekly
from . import snapshot as live

DB_PATH = Path(os.environ.get("TIPOFF_DB", DEFAULT_DB))
RULES_PATH = Path(os.environ.get("TIPOFF_RULES", ROOT / "rules.json"))
REPORTS = ROOT / "reports"
DIST = ROOT / "web" / "dist"
LEAGUES = [
    {"id": "nba", "label": "NBA", "live": True},
    {"id": "nfl", "label": "NFL", "live": False},
    {"id": "mlb", "label": "MLB", "live": False},
    {"id": "nhl", "label": "NHL", "live": False},
]

live.load_env()
app = FastAPI(title="Tip-Off Desk")


class DateBody(BaseModel):
    date: str


OPEN_PATHS = {"/api/session", "/api/login", "/api/logout"}


@app.middleware("http")
async def sign_in_gate(request: Request, call_next):
    """Every /api call needs a session when a password is set; without one, only this computer."""
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        if auth.password():
            if not auth.valid(ROOT, request.cookies.get(auth.COOKIE)):
                return JSONResponse({"detail": "Sign in to use the desk."}, status_code=401)
        elif not auth.is_local(request):
            return JSONResponse({"detail": "Set TIPOFF_PASSWORD in .env before opening the desk to other "
                                           "devices."}, status_code=403)
    return await call_next(request)


class Login(BaseModel):
    password: str


@app.get("/api/session")
async def session(request: Request):
    required = bool(auth.password())
    return {"required": required,
            "signed_in": (not required and auth.is_local(request)) or auth.valid(ROOT, request.cookies.get(auth.COOKIE))}


@app.post("/api/login")
async def login(body: Login, request: Request):
    if not auth.password():
        raise HTTPException(400, "No password is set on this desk.")
    who = auth.client_id(request)
    if auth.throttled(who):
        raise HTTPException(429, "Too many wrong passwords. Wait 15 minutes and try again.")
    if not auth.check(body.password):
        auth.note_failure(who)
        raise HTTPException(401, "That password isn't right.")
    resp = JSONResponse({"signed_in": True})
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(auth.COOKIE, auth.issue(ROOT), max_age=auth.SESSION_SECONDS, httponly=True,
                    samesite="lax", secure=https, path="/")
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"signed_in": False})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


_state = {}


def con():
    # Endpoints are async with no awaits inside, so requests run one at a time on the event
    # loop; the connection only needs to tolerate the loop thread differing from its creator.
    if "con" not in _state:
        _state["con"] = connect(DB_PATH, check_same_thread=False)
    return _state["con"]


def features():
    if "fs" not in _state:
        _state["fs"] = FeatureStore(con())
    return _state["fs"]


def cfg():
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_bets(date, statuses=("card", "locked")):
    q = (f"SELECT b.*, e.away_team, e.home_team, e.commence_time FROM bets b LEFT JOIN events e USING (event_id)"
         f" WHERE b.paper=0 AND b.slate_date=? AND b.status IN ({','.join('?' * len(statuses))}) ORDER BY b.id")
    return [dict(r) for r in con().execute(q, (date, *statuses))]


# ---------- meta and slate ----------

def is_sample():
    """Judge by the data, not the filename: tipoff.sample_data writes event ids as 'ev_<game>',
    while The Odds API uses 32-character hex ids."""
    row = con().execute("SELECT event_id FROM events LIMIT 1").fetchone()
    return bool(row) and row[0].startswith("ev_")


def bet_label(player, side, point, stat):
    """'Kel Reid · Threes O 1.5', the same words the board and ticket use."""
    return f"{player} · {STAT_LABEL.get(stat, stat)} {side[0].upper()} {point:g}"


_BACKTEST_BET = re.compile(r"^(.*) ([ou])([\d.]+) (\w+)$")


def _backtest_label(text):
    m = _BACKTEST_BET.match(text)
    return bet_label(m[1], m[2], float(m[3]), m[4]) if m else text

@app.get("/api/meta")
async def meta():
    dates = slate_dates(con())
    today = str(datetime.now(live.ET).date())
    if os.environ.get("ODDS_API_KEY") and today not in dates:
        dates = [today] + dates  # tonight is pullable even before its first snapshot
    c = cfg()
    graded = [dict(r) for r in con().execute("SELECT clv FROM bets WHERE paper=0 AND status='graded' AND clv IS NOT NULL")]
    clvs = [g["clv"] for g in graded]
    return {
        "db": DB_PATH.name, "sample": is_sample(), "dates": dates[:60],
        "default_date": dates[0] if dates else None, "settings": c["settings"], "leagues": LEAGUES,
        "live_clv": {"n": len(clvs), "avg": sum(clvs) / len(clvs) if clvs else None},
        "odds_key": bool(os.environ.get("ODDS_API_KEY")), "today": today,
        "credits_remaining": _state.get("credits_remaining"), "markets": len(live.DEFAULT_MARKETS),
    }


@app.post("/api/refresh")
async def refresh(body: DateBody):
    """Pull live odds now for tonight's games that haven't tipped. Costs credits."""
    if not os.environ.get("ODDS_API_KEY"):
        raise HTTPException(400, "No odds key yet. Put ODDS_API_KEY in .env and restart the server.")
    if body.date != str(datetime.now(live.ET).date()):
        raise HTTPException(400, "Live odds can only be pulled for today's slate.")
    credits = live.Credits()
    try:
        n = live.refresh(con(), datetime.fromisoformat(body.date).date(), os.environ["ODDS_API_KEY"], credits)
    except SystemExit as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"The Odds API call failed: {e}")
    _state["credits_remaining"] = credits.remaining
    return {"games": n, "credits_used": credits.used, "credits_remaining": credits.remaining}


@app.get("/api/slate")
async def slate(date: str):
    card = open_bets(date)
    games = price_slate(con(), features(), cfg(), date, card=card)
    return {"date": date, "games": games}


@app.get("/api/news")
async def news(date: str, player: str):
    """A player is ruled out: their teammates' markets on tonight's slate, best edge first."""
    games = price_slate(con(), features(), cfg(), date, card=open_bets(date))
    rows = [m | {"game": g} for g in games for m in g["markets"]]
    out = next((m for m in rows if m["name_key"] == player), None)
    if out is None:
        raise HTTPException(404, "That player has no markets on this slate.")
    mates = [m for m in rows if m["team"] == out["team"] and m["name_key"] != player]
    own = [m for m in rows if m["name_key"] == player]
    strip = lambda m: {k: v for k, v in m.items() if k != "game"} | {
        "matchup": f"{m['game']['away']} @ {m['game']['home']}", "commence_time": m["game"]["commence_time"],
        "snapshot_ts": m["game"]["snapshot_ts"]}
    return {"player": out["player"], "team": out["team"],
            "teammates": [strip(m) for m in sorted(mates, key=lambda m: -m["edge"])],
            "own": [strip(m) for m in own]}


# ---------- suggestions and Claude's notes ----------

def _with_game(games):
    return [m | {"matchup": f"{g['away']} @ {g['home']}", "commence_time": g["commence_time"]}
            for g in games for m in g["markets"]]


def _candidates(date):
    """What Claude reviews: the legs already on the card plus tonight's suggested additions."""
    card = open_bets(date)
    games = price_slate(con(), features(), cfg(), date, card=card)
    picks = {m["id"] for m in suggest(games, card, cfg())}
    return [m for m in _with_game(games) if m["on_card"] or m["id"] in picks]


@app.get("/api/suggest")
async def suggested(date: str):
    card = open_bets(date)
    games = price_slate(con(), features(), cfg(), date, card=card)
    ids = [m["id"] for m in suggest(games, card, cfg())]
    by_id = {m["id"]: m for m in _with_game(games)}
    legs = [by_id[i] for i in ids]
    return {"date": date, "legs": legs, "risk": round(sum(m["stake"] for m in legs), 2)}


class AddSuggested(BaseModel):
    date: str
    exclude: list[str] = []


@app.post("/api/card/suggested")
async def add_suggested(body: AddSuggested):
    """Add the suggested legs at once (the same checks as adding one by one), minus any the user
    chose to leave out, such as legs Claude flagged "skip"."""
    if any(l["status"] != "card" for l in open_bets(body.date, ("card", "locked", "graded"))):
        raise HTTPException(409, "Tonight's card is locked. Unlock it to make changes.")
    card = open_bets(body.date)
    games = price_slate(con(), features(), cfg(), body.date, card=card)
    snaps = {g["event_id"]: g["snapshot_ts"] for g in games}
    for m in suggest(games, card, cfg()):
        if m["id"] in body.exclude:
            continue
        con().execute(
            "INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair, edge,"
            " stake, snapshot_ts, added_at, context) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (body.date, m["event_id"], m["market"], m["name_key"], m["player"], m["side"], m["point"], m["book"],
             m["price"], m["fair"], m["edge"], m["stake"], snaps[m["event_id"]], now(), json.dumps(m["context"])))
    con().commit()
    return _card(body.date)


@app.get("/api/injuries")
async def injuries(date: str):
    """Injury statuses for players with props on this slate. Read straight from the feed (cached a few
    minutes); the watcher (python -m tipoff.injuries) keeps its own records for alerts."""
    import time as _t
    cached = _state.get("injury_feed")
    if not cached or _t.time() - cached[0] > 180:
        try:
            _state["injury_feed"] = cached = (_t.time(), injury_feed.fetch())
        except Exception:
            if not cached:
                return {"date": date, "players": [], "error": "The injury feed didn't answer. Try again shortly."}
    tonight = injury_feed.slate(con(), date)
    players = [i | {"matchup": tonight[i["name_key"]][2]} for i in cached[1]
               if i["name_key"] in tonight and i["status"] != "Active"]
    return {"date": date, "players": sorted(players, key=lambda i: i["updated"], reverse=True)}


@app.get("/api/journal")
async def journal_entries(limit: int = 30):
    """The paper trader's plain-English journal: decisions as they happen, morning recaps."""
    from . import journal
    return {"entries": journal.entries(con(), limit)}


@app.get("/api/notes")
async def get_notes(date: str):
    return {"date": date, "notes": claude_notes.load(con(), date),
            "claude_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/notes")
async def make_notes(body: DateBody):
    """Ask Claude to check news on the card and suggested legs. Costs a few cents of API usage."""
    legs = _candidates(body.date)
    if not legs:
        raise HTTPException(400, "Nothing to check yet: the card is empty and nothing is suggested.")
    ctx = [claude_notes.leg_context(con(), features(), m, body.date) for m in legs]
    try:
        notes = claude_notes.ask_claude(ctx, body.date)
    except claude_notes.NotesError as e:
        raise HTTPException(502, str(e))
    claude_notes.save(con(), body.date, notes, {m["id"]: m["price"] for m in legs})
    return {"date": body.date, "notes": claude_notes.load(con(), body.date), "checked": len(legs)}


# ---------- tonight's card ----------

class AddLeg(BaseModel):
    date: str
    market_id: str


@app.get("/api/card")
async def card(date: str):
    return _card(date)


def _card(date):
    c = cfg()
    s, rules = c["settings"], c["rules"]
    legs = open_bets(date, ("card", "locked", "graded"))
    min_edge = rule_params(rules, "min_edge", "min", 0.02)
    per_player = rule_params(rules, "max_per_player", "max", 2)
    per_night = rule_params(rules, "max_per_night", "max", 12)
    cap = s.get("nightly_risk_cap", 0.08) * s["bankroll"]
    risk = sum(l["stake"] for l in legs)
    counts = {}
    for l in legs:
        counts[l["name_key"]] = counts.get(l["name_key"], 0) + 1
    low = [l for l in legs if l["edge"] < min_edge]
    over = [l for l in legs if counts[l["name_key"]] > per_player]
    checks = [
        {"ok": not low, "text": f"Every bet has {min_edge:.0%}+ value at Hard Rock",
         "fail": f"Less than {min_edge:.0%} value at Hard Rock", "legs": [l["id"] for l in low]},
        {"ok": not over, "text": f"No more than {per_player} bets on one player",
         "fail": f"Over the {per_player}-per-player cap", "legs": [l["id"] for l in over]},
        {"ok": len(legs) <= per_night, "text": f"No more than {per_night} bets tonight",
         "fail": f"More than {per_night} bets tonight", "legs": []},
        {"ok": risk <= cap + 1e-9, "text": f"Risk within the nightly cap (${cap:,.0f})",
         "fail": f"Risk over the ${cap:,.0f} nightly cap", "legs": []},
    ]
    locked = bool(legs) and all(l["status"] in ("locked", "graded") for l in legs)
    return {
        "date": date, "legs": legs, "risk": round(risk, 2), "cap": round(cap, 2), "checks": checks,
        "locked": locked, "locked_at": legs[0]["locked_at"] if locked else None,
        "can_lock": bool(legs) and not locked and all(ch["ok"] for ch in checks),
    }


@app.post("/api/card/legs")
async def add_leg(body: AddLeg):
    if any(l["status"] != "card" for l in open_bets(body.date, ("card", "locked", "graded"))):
        raise HTTPException(409, "Tonight's card is locked. Unlock it to make changes.")
    games = price_slate(con(), features(), cfg(), body.date, card=open_bets(body.date))
    m = next((m for g in games for m in g["markets"] if m["id"] == body.market_id), None)
    if m is None:
        raise HTTPException(404, "That market is no longer on the board. Refresh and try again.")
    if m["on_card"]:
        return _card(body.date)
    if m["blocked"]:
        rule = next(f["text"] for f in m["flags"] if f["blocks"])
        raise HTTPException(409, f"Held out by a confirmed rule: {rule}.")
    snap = next(g["snapshot_ts"] for g in games if g["event_id"] == m["event_id"])
    con().execute(
        "INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair, edge,"
        " stake, snapshot_ts, added_at, context) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (body.date, m["event_id"], m["market"], m["name_key"], m["player"], m["side"], m["point"], m["book"],
         m["price"], m["fair"], m["edge"], m["stake"], snap, now(), json.dumps(m["context"])))
    con().commit()
    return _card(body.date)


@app.delete("/api/card/legs/{bet_id}")
async def remove_leg(bet_id: int):
    row = con().execute("SELECT slate_date, status FROM bets WHERE id=?", (bet_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "That leg is already gone.")
    if row["status"] != "card":
        raise HTTPException(409, "Tonight's card is locked. Unlock it to make changes.")
    con().execute("DELETE FROM bets WHERE id=?", (bet_id,))
    con().commit()
    return _card(row["slate_date"])


@app.post("/api/card/clear")
async def clear(body: DateBody):
    con().execute("DELETE FROM bets WHERE paper=0 AND slate_date=? AND status='card'", (body.date,))
    con().commit()
    return _card(body.date)


@app.post("/api/card/lock")
async def lock(body: DateBody):
    c = _card(body.date)
    if not c["can_lock"]:
        failed = [ch["text"] for ch in c["checks"] if not ch["ok"]]
        raise HTTPException(409, "Can't lock yet: " + ("; ".join(failed) if failed else "the card is empty") + ".")
    con().execute("UPDATE bets SET status='locked', locked_at=? WHERE paper=0 AND slate_date=? AND status='card'",
                  (now(), body.date))
    con().commit()
    return _card(body.date)


@app.post("/api/card/unlock")
async def unlock(body: DateBody):
    con().execute("UPDATE bets SET status='card', locked_at=NULL, placed=0 WHERE paper=0 AND slate_date=? AND status='locked'",
                  (body.date,))
    con().commit()
    return _card(body.date)


class Placed(BaseModel):
    placed: bool


@app.patch("/api/bets/{bet_id}")
async def mark_placed(bet_id: int, body: Placed):
    row = con().execute("SELECT slate_date FROM bets WHERE id=?", (bet_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "That bet doesn't exist.")
    con().execute("UPDATE bets SET placed=? WHERE id=?", (int(body.placed), bet_id))
    con().commit()
    return _card(row["slate_date"])


# ---------- grading and ledger ----------

def grade():
    """Grade finished bets and Claude's judged legs (see tipoff/grading.py)."""
    c = cfg()
    claude_notes.ensure_table(con())
    grading.grade_notes(con(), c)
    grading.grade_marks(con(), c)
    return grading.grade_bets(con(), c)


def _latest(pattern):
    files = sorted(REPORTS.glob(pattern))
    return files[-1] if files else None


@app.get("/api/ledger")
async def ledger(source: str = "live", strategy: str = "current"):
    if source == "backtest":
        path = REPORTS / "ledger.json"
        if not path.exists():
            raise HTTPException(404, "No backtest ledger yet. Run python -m tipoff.backtest first.")
        rows = json.loads(path.read_text(encoding="utf-8"))
        bets = [{"date": r["date"], "game": r["game"], "bet": _backtest_label(r["bet"]), "price": r["took"],
                 "close_price": r["close"], "clv": r["clv"], "edge": r["edge"], "result": r["result"],
                 "stake": r["stake"], "pnl": r["pnl"]} for r in rows]
    else:
        grade()
        bets = []
        q, args = ("SELECT * FROM bets WHERE paper=1 AND strategy=? AND status='graded' ORDER BY slate_date, id",
                   (strategy,)) if source == "paper" else (
                   "SELECT * FROM bets WHERE paper=0 AND status='graded' ORDER BY slate_date, id", ())
        for r in con().execute(q, args):
            r = dict(r)
            d = (1 + r["price"] / 100) if r["price"] > 0 else (1 + 100 / -r["price"])
            pnl = r["stake"] * (d - 1) if r["result"] == "win" else (-r["stake"] if r["result"] == "loss" else 0)
            bets.append({"date": r["slate_date"], "game": r["event_id"], "id": r["id"],
                         "bet": bet_label(r["player"], r["side"], r["point"], MARKET_STAT[r["market"]]),
                         "price": r["price"], "close_price": r["close_price"], "clv": r["clv"], "edge": r["edge"],
                         "result": r["result"], "stake": r["stake"], "pnl": round(pnl, 2), "actual": r["actual"]})
    summary = metrics([b for b in bets if b["result"] != "void"]) if bets else metrics([])
    nights = {}
    for b in bets:
        n = nights.setdefault(b["date"], {"date": b["date"], "bets": 0, "clvs": [], "pnl": 0.0, "stake": 0.0})
        n["bets"] += 1
        n["pnl"] += b["pnl"]
        n["stake"] += b["stake"]
        if b["clv"] is not None:
            n["clvs"].append(b["clv"])
    by_night = [{"date": n["date"], "bets": n["bets"], "pnl": round(n["pnl"], 2), "stake": round(n["stake"], 2),
                 "avg_clv": sum(n["clvs"]) / len(n["clvs"]) if n["clvs"] else None} for n in nights.values()]
    paper, waiting = None, []
    if source == "paper":
        from .paper import START_BANKROLL, bankroll, strategies
        # This strategy's bets still waiting on the game and the box score, so tonight's picks show before grading.
        for r in con().execute("SELECT b.*, e.away_team, e.home_team FROM bets b LEFT JOIN events e USING (event_id)"
                               " WHERE b.paper=1 AND b.strategy=? AND b.status='locked' ORDER BY b.slate_date, b.id",
                               (strategy,)):
            waiting.append({"id": r["id"], "date": r["slate_date"],
                            "game": f"{r['away_team']} @ {r['home_team']}" if r["away_team"] else r["event_id"],
                            "bet": bet_label(r["player"], r["side"], r["point"], MARKET_STAT[r["market"]]),
                            "price": r["price"], "edge": r["edge"], "stake": r["stake"]})
        paper = []
        for st in strategies(cfg()):
            clvs = [r[0] for r in con().execute("SELECT clv FROM bets WHERE paper=1 AND strategy=? AND status='graded'"
                                                " AND clv IS NOT NULL", (st["id"],))]
            pending = con().execute("SELECT COUNT(*) FROM bets WHERE paper=1 AND strategy=? AND status='locked'",
                                    (st["id"],)).fetchone()[0]
            paper.append({"id": st["id"], "name": st["name"], "graded": len(clvs), "pending": pending,
                          "avg_clv": sum(clvs) / len(clvs) if clvs else None,
                          "bankroll": bankroll(con(), st["id"]), "start": START_BANKROLL})
        try:  # the control group: every prop recorded at decision time, picked or not
            clvs = [r[0] for r in con().execute("SELECT clv FROM marks WHERE graded=1 AND clv IS NOT NULL")]
            pending = con().execute("SELECT COUNT(*) FROM marks WHERE graded=0").fetchone()[0]
        except Exception:
            clvs, pending = [], 0
        paper.append({"id": "_all", "name": "Every prop, no picking (control)", "graded": len(clvs),
                      "pending": pending, "avg_clv": sum(clvs) / len(clvs) if clvs else None,
                      "bankroll": None, "start": None})
    return {"source": source, "paper": paper, "waiting": waiting, "summary": summary, "nights": by_night,
            "bets": bets[-200:]}


# ---------- rulebook ----------

@app.get("/api/rules")
async def rules():
    c = cfg()
    report_path = _latest("backtest-*.json")
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path else None
    verdicts = {r["id"]: r for r in (report or {}).get("rules", [])}
    return {
        "rules": [r | {"backtest": verdicts.get(r["id"])} for r in c["rules"]],
        "report": None if not report else {
            "generated": report["generated"], "db": Path(report["db"]).name, "holdout": report["holdout"],
            "overall": report["overall"]},
    }


class Status(BaseModel):
    status: str


@app.post("/api/rules/{rule_id}/status")
async def set_status(rule_id: str, body: Status):
    """The user's own decision from the Rulebook screen (they confirm it in the UI first)."""
    if body.status not in ("confirmed", "testing", "retired"):
        raise HTTPException(400, "Status must be confirmed, testing or retired.")
    c = cfg()
    rule = next((r for r in c["rules"] if r["id"] == rule_id), None)
    if rule is None:
        raise HTTPException(404, "No rule with that id.")
    if rule["kind"] == "gate":
        raise HTTPException(409, "Gate rules are always on; change their numbers in rules.json.")
    rule["status"] = body.status
    RULES_PATH.write_text(_dump_rules(c), encoding="utf-8")
    return rules()


# ---------- weekly review ----------

REVIEW_LOG = """
CREATE TABLE IF NOT EXISTS review_log (
    at         TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    proposal   TEXT NOT NULL,
    decision   TEXT NOT NULL      -- applied / dismissed
);
"""


def _review():
    grade()
    rep = weekly.run(con(), cfg())
    con().executescript(REVIEW_LOG)
    recent = {r[0]: r[1] for r in con().execute(
        "SELECT finding_id, decision FROM review_log WHERE at >= datetime('now', '-7 days') ORDER BY at")}
    for f in rep["findings"]:
        f["decided"] = recent.get(f["id"]) if f.get("proposal") else None
    return rep


@app.get("/api/review")
async def review():
    return _review()


class Decision(BaseModel):
    id: str


@app.post("/api/review/apply")
async def apply_proposal(body: Decision):
    """The user applies one proposal from the Rulebook (after confirming it there)."""
    f = next((f for f in weekly.run(con(), cfg())["findings"] if f["id"] == body.id and f.get("proposal")), None)
    if f is None:
        raise HTTPException(409, "That proposal no longer stands with the latest bets. Reload the review.")
    p, c = f["proposal"], cfg()
    if p["type"] == "strategy":  # adopt a paper strategy's overrides for the real card
        for k, v in p["overrides"].items():
            rule = next((r for r in c["rules"] if r["id"] == k), None)
            if rule is not None:
                rule.setdefault("params", {})["min"] = v
            else:
                c["settings"][k] = v
    elif p["type"] == "rule_status":
        rule = next(r for r in c["rules"] if r["id"] == p["rule"])
        rule["status"] = p["value"]
    elif p.get("rule"):
        rule = next(r for r in c["rules"] if r["id"] == p["rule"])
        rule.setdefault("params", {})[p["key"]] = p["value"]
    else:
        c["settings"][p["key"]] = p["value"]
    RULES_PATH.write_text(_dump_rules(c), encoding="utf-8")
    _log_decision(body.id, p, "applied")
    return _review()


@app.post("/api/review/dismiss")
async def dismiss_proposal(body: Decision):
    f = next((f for f in weekly.run(con(), cfg())["findings"] if f["id"] == body.id), None)
    _log_decision(body.id, (f or {}).get("proposal") or {}, "dismissed")
    return _review()


def _log_decision(fid, proposal, decision):
    con().executescript(REVIEW_LOG)
    con().execute("INSERT INTO review_log VALUES (datetime('now'), ?, ?, ?)", (fid, json.dumps(proposal), decision))
    con().commit()


def _dump_rules(c):
    # Keep rules.json readable: one rule per line, like the hand-written file.
    lines = ["{", '  "settings": ' + json.dumps(c["settings"]) + ",", '  "rules": [']
    lines += ["    " + json.dumps(r) + ("," if i < len(c["rules"]) - 1 else "") for i, r in enumerate(c["rules"])]
    lines += ["  ]", "}", ""]
    return "\n".join(lines)


# ---------- the built front end ----------

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    if a.host not in auth.LOCAL and not auth.password():
        raise SystemExit("Set TIPOFF_PASSWORD in .env before listening on " + a.host + ".")
    os.environ["TIPOFF_DB"] = a.db
    DB_PATH = Path(a.db)
    uvicorn.run(app, host=a.host, port=a.port, proxy_headers=True)
