"""The paper trader's journal, in plain words: why it bet what it bet, and next morning, how it went.

    python -m tipoff.journal --recap                 # recap yesterday (run after the morning grading)
    python -m tipoff.journal --recap --date 2026-10-22
    python -m tipoff.journal --recap --league nfl    # the NFL's (skips quietly after a day without NFL games)

Decision entries are written by tipoff.paper as it bets each game. The morning recap is written by
Claude from the graded numbers only (when ANTHROPIC_API_KEY is set), otherwise from a template, and
is pushed to your phone through ntfy when NTFY_TOPIC is set.
"""
import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import leagues
from .leagues import stat_of, stat_words
from .pricing import ev

TABLE = """
CREATE TABLE IF NOT EXISTS journal (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    day     TEXT NOT NULL,       -- the slate the entry is about
    at      TEXT NOT NULL,
    kind    TEXT NOT NULL,       -- decision / recap
    title   TEXT NOT NULL,
    body    TEXT NOT NULL
);
"""
STAT = {s: leagues.NBA.words(s) for s in leagues.NBA.stat_label}  # NBA names; every league: stat_words()
MIN_SAMPLE = 30


def american(p):
    return f"+{p}" if p > 0 else f"−{abs(p)}"


def add(con, day, kind, title, body):
    con.executescript(TABLE)
    con.execute("INSERT INTO journal (day, at, kind, title, body) VALUES (?,?,?,?,?)",
                (day, datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, title, body))
    con.commit()


def entries(con, limit=30):
    con.executescript(TABLE)
    return [dict(r) for r in con.execute("SELECT * FROM journal ORDER BY at DESC LIMIT ?", (limit,))]


# ---------- during the night ----------

def why(m, note=None):
    """One bet, explained the way you'd explain it to a friend."""
    side = "OVER" if m["side"] == "Over" else "UNDER"
    line = (f"{m['player']} {side} {m['point']:g} {m['stat_label'].lower()}: bet ${m['stake']:.0f} at Hard Rock "
            f"{american(m['price'])}. The other books make it worth about {american(m['fair_american'])}, so "
            f"Hard Rock is paying more than it should: about ${m['edge'] * 100:.0f} profit per $100, on average.")
    if note:
        line += f" Claude's news check: {note['verdict']}, {note['note']}"
    return line


def decision_entry(con, day, games, placed, marks, notes, min_edge):
    """What the paper trader did on these games, and what it passed on."""
    names = ", ".join(f"{g['away']} @ {g['home']}" for g in games)
    picks = placed.get("current", [])
    title = (f"{names}: {len(picks)} paper {'bet' if len(picks) == 1 else 'bets'}" if picks
             else f"{names}: no paper bets")
    lines = []
    if picks:
        lines.append("Took these, by today's rules:")
        lines += [f"- {why(m, notes.get(m['id']))}" for m in picks]
    taken = {m["id"] for m in picks}
    rest = sorted((m for m in marks if m["id"] not in taken), key=lambda m: -m["edge"])
    if rest:
        best = rest[0]
        side = "over" if best["side"] == "Over" else "under"
        lines.append(f"Passed on {len(rest)} other props. The closest was {best['player']} {side} {best['point']:g} "
                     f"{best['stat_label'].lower()} at {best['edge'] * 100:+.1f}% value"
                     + (f", short of the {min_edge:.0%} bar." if best["edge"] < min_edge
                        else f", held out by: {', '.join(f['text'] for f in best['flags'] if f['blocks'])}."))
    if not picks:
        lines.append("Hard Rock's prices on these games looked fair, so it sat them out. That's normal.")
    from .paper import DEFAULT_STRATEGIES
    names = {st["id"]: st["name"] for st in DEFAULT_STRATEGIES}
    others = [f"“{names.get(s, s)}” {len(p)}" for s, p in placed.items() if s != "current"]
    if others:
        lines.append("The test strategies took: " + ", ".join(others) + " (compared in the Ledger's Paper tab).")
    add(con, day, "decision", title, "\n".join(lines))


# ---------- the morning after ----------

def night_numbers(con, day):
    """Everything the recap may say, as numbers. The recap writer may use nothing else."""
    from .paper import START_BANKROLL, bankroll
    out = {"date": day, "strategies": []}
    for sid, name in con.execute("SELECT DISTINCT strategy, strategy FROM bets WHERE paper=1 AND slate_date=?", (day,)):
        rows = [dict(r) for r in con.execute("SELECT * FROM bets WHERE paper=1 AND strategy=? AND slate_date=?",
                                             (sid, day))]
        graded = [r for r in rows if r["status"] == "graded"]
        pnl = 0.0
        bets = []
        for r in graded:
            dec = 1 + r["price"] / 100 if r["price"] > 0 else 1 + 100 / -r["price"]
            p = r["stake"] * (dec - 1) if r["result"] == "win" else (-r["stake"] if r["result"] == "loss" else 0)
            pnl += p
            bets.append({"bet": f"{r['player']} {r['side'].lower()} {r['point']:g} {stat_words(stat_of(r['market']))}",
                         "price": american(r["price"]), "stake": round(r["stake"]), "result": r["result"],
                         "finished_with": r["actual"], "profit": round(p, 2),
                         "beat_the_close_by": None if r["clv"] is None else f"{r['clv'] * 100:+.1f}%"})
        clvs = [r["clv"] for r in graded if r["clv"] is not None]
        out["strategies"].append({
            "id": sid, "bets": len(rows), "graded": len(graded), "still_waiting": len(rows) - len(graded),
            "wins": sum(r["result"] == "win" for r in graded), "losses": sum(r["result"] == "loss" for r in graded),
            "voids": sum(r["result"] == "void" for r in graded), "profit": round(pnl, 2),
            "bankroll_now": bankroll(con, sid), "bankroll_start": START_BANKROLL,
            "beat_the_close": f"{sum(c > 0 for c in clvs)} of {len(clvs)}",
            "avg_vs_close": None if not clvs else f"{sum(clvs) / len(clvs) * 100:+.1f}%", "bet_list": bets})
    try:
        marks = con.execute("SELECT stat, side, price, p_market, clv FROM marks WHERE slate_date=? AND graded=1"
                            " AND clv IS NOT NULL", (day,)).fetchall()
    except Exception:
        marks = []
    if marks:
        def avg(rows):
            return None if not rows else f"{sum(r[4] for r in rows) / len(rows) * 100:+.1f}% over {len(rows)} props"
        out["all_props"] = {
            "graded": len(marks),
            "value_2pct_or_more": avg([r for r in marks if ev(r[3], r[2]) >= 0.02]),
            "value_below_2pct": avg([r for r in marks if ev(r[3], r[2]) < 0.02]),
            "by_stat": {stat_words(s): avg([r for r in marks if r[0] == s]) for s in sorted({r[0] for r in marks})},
            "overs": avg([r for r in marks if r[1] == "Over"]), "unders": avg([r for r in marks if r[1] == "Under"])}
    total = con.execute("SELECT COUNT(*) FROM bets WHERE paper=1 AND strategy='current' AND status='graded'"
                        ).fetchone()[0]
    out["season_so_far"] = {"graded_paper_bets": total, "enough_to_judge": total >= MIN_SAMPLE,
                            "needed_to_judge": MIN_SAMPLE}
    return out


RECAP_PROMPT = """You write the morning recap for a two-person sports betting desk's paper trader (pretend money).
Readers are smart but not betting experts. Use ONLY the numbers in the JSON below; never invent or estimate a number.

Write plain text, no markdown headings, in this shape:
1. One headline sentence: how much the paper bankroll ("current" strategy = today's rules) made or lost last night, and
   where it stands now.
2. "What happened": 2-4 short bullets ("- ") naming the bets in plain words and how each went.
3. "Beating the market": one or two sentences on whether the prices it took beat the closing line, and why that matters
   more than wins and losses over a few nights.
4. "What it's learning": 1-3 bullets from all_props and the other strategies. Say plainly when the sample is too small
   to conclude anything (season_so_far.enough_to_judge is false); never claim a pattern from one night.
Keep it under 180 words. No hype, no betting advice beyond what the numbers show."""


def recap(con, day, notify=True, league=None):
    """The morning recap for one league's paper trader. NBA plays nearly every night; the NFL plays
    a few days a week, so for other leagues a day without games is skipped quietly (no entry, no push)."""
    lg = leagues.get(league)
    if lg.id != "nba" and not con.execute("SELECT 1 FROM events WHERE game_date=? LIMIT 1", (day,)).fetchone():
        return None, f"No {lg.label} games on {day}; nothing to recap."
    nums = night_numbers(con, day)
    nums["league"] = lg.label
    if not nums["strategies"]:
        text = f"No paper bets were graded for {day}."
    elif os.environ.get("ANTHROPIC_API_KEY"):
        text = claude_recap(nums) or template_recap(nums)
    else:
        text = template_recap(nums)
    cur = next((s for s in nums["strategies"] if s["id"] == "current"), None)
    when = "Last night" if lg.id == "nba" else f"{lg.label} {_weekday(day)}"
    title = (f"{when}: {'+' if cur['profit'] >= 0 else '−'}${abs(cur['profit']):.0f} "
             f"(bankroll ${cur['bankroll_now']:,.0f})") if cur else (
             f"Recap for {day}" if lg.id == "nba" else f"{lg.label} recap for {day}")
    add(con, day, "recap", title, text)
    if notify:
        from .injuries import DESK_URL, notify as push
        push(title, text[:900], f"{DESK_URL}/#/ledger", lg.ntfy_tag)
    return title, text


def _weekday(day):
    return date.fromisoformat(day).strftime("%A")


def claude_recap(nums):
    import anthropic
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-opus-5-5", max_tokens=2000, output_config={"effort": "low"},
            messages=[{"role": "user", "content": RECAP_PROMPT + "\n\n" + json.dumps(nums, indent=1)}])
    except anthropic.AnthropicError as e:
        print(f"Claude recap unavailable ({e}); using the template.")
        return None
    if resp.stop_reason == "refusal":
        return None
    return next((b.text for b in resp.content if b.type == "text"), None)


def template_recap(nums):
    cur = next((s for s in nums["strategies"] if s["id"] == "current"), nums["strategies"][0])
    sign = "+" if cur["profit"] >= 0 else "−"
    lines = [f"The paper bankroll went {sign}${abs(cur['profit']):.2f} last night and is now ${cur['bankroll_now']:,.2f}.",
             "What happened:"]
    lines += [f"- {b['bet']} at {b['price']}: {b['result']}" + (f", beat the close by {b['beat_the_close_by']}"
                                                              if b["beat_the_close_by"] else "") for b in cur["bet_list"]]
    lines.append(f"Beat the close on {cur['beat_the_close']} bets ({cur['avg_vs_close'] or 'n/a'} on average). "
                 "That matters more than wins and losses over a few nights.")
    s = nums["season_so_far"]
    if not s["enough_to_judge"]:
        lines.append(f"Too early to learn anything firm: {s['graded_paper_bets']} graded paper bets so far, "
                     f"{s['needed_to_judge']}+ needed.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    from .db import connect
    from .grading import grade_bets, grade_marks, grade_notes
    from .notes import ensure_table
    from .snapshot import ET, load_env

    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--recap", action="store_true")
    ap.add_argument("--date", default=str(datetime.now(ET).date() - timedelta(days=1)))
    ap.add_argument("--db", default=None)
    leagues.add_argument(ap)
    a = ap.parse_args()
    lg = leagues.get(a.league)
    con = connect(a.db, league=lg)
    cfg = json.loads(lg.rules_path.read_text(encoding="utf-8"))
    ensure_table(con)
    grade_notes(con, cfg), grade_marks(con, cfg), grade_bets(con, cfg)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.recap:
        title, text = recap(con, a.date, league=lg)
        print(title or "", "\n", text, sep="")
    else:
        for e in entries(con, 10):
            print(f"[{e['day']} {e['kind']}] {e['title']}\n{e['body']}\n")
