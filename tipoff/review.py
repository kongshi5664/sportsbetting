"""Weekly review: what the graded bets say about the rules, the settings and Claude's calls.

    python -m tipoff.review            # writes reports/review-YYYY-MM-DD.md and .json

It judges everything by closing-line value (did the price move your way after you bet), never by
wins and losses, and only proposes a change when there are enough bets on both sides of a
comparison and the gap is clear of the noise (about two standard errors). Proposals are
suggestions: nothing in rules.json changes until a person applies one from the Rulebook.
"""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from .backtest import ROOT, _rule_matches

MIN_N = 30   # bets needed on each side of a comparison before proposing anything
Z = 2.0      # how clear of the noise a gap has to be

BUCKETS = [("2–3%", 0.02, 0.03), ("3–4%", 0.03, 0.04), ("4–6%", 0.04, 0.06), ("6%+", 0.06, 9.0)]


def stats(clvs):
    n = len(clvs)
    if not n:
        return {"n": 0, "avg": None, "se": None, "beat": None}
    avg = sum(clvs) / n
    se = math.sqrt(sum((c - avg) ** 2 for c in clvs) / (n - 1)) / math.sqrt(n) if n > 1 else None
    return {"n": n, "avg": avg, "se": se, "beat": sum(c > 0 for c in clvs) / n}


def gap(a, b):
    """(difference in average CLV, z score) between two groups, or (None, None) if either is thin."""
    if a["n"] < MIN_N or b["n"] < MIN_N or not a["se"] or not b["se"]:
        return a["avg"] - b["avg"] if a["avg"] is not None and b["avg"] is not None else None, None
    d = a["avg"] - b["avg"]
    return d, d / math.sqrt(a["se"] ** 2 + b["se"] ** 2)


def load_bets(con):
    out = []
    for r in con.execute("SELECT * FROM bets WHERE status='graded' AND clv IS NOT NULL"):
        r = dict(r)
        r["ctx"] = json.loads(r["context"]) if r.get("context") else None
        out.append(r)
    return out


def rule_findings(bets, rules):
    found = []
    with_ctx = [b for b in bets if b["ctx"]]
    for rule in rules:
        if rule["kind"] == "gate" or rule["status"] == "retired":
            continue
        try:
            hit = [_rule_matches(rule, b["ctx"]) for b in with_ctx]
        except KeyError:
            continue  # a rule with no predicate yet
        a = stats([b["clv"] for b, h in zip(with_ctx, hit) if h])
        b = stats([b["clv"] for b, h in zip(with_ctx, hit) if not h])
        d, z = gap(a, b)
        good = (z is not None) and ((z >= Z) if rule["kind"] == "prefer" else (z <= -Z))
        bad = (z is not None) and ((z <= -Z) if rule["kind"] == "prefer" else (z >= Z))
        proposal = None
        if rule["status"] == "testing" and good:
            proposal = {"type": "rule_status", "rule": rule["id"], "value": "confirmed"}
            verdict = "Holding up: propose promoting it"
        elif rule["status"] == "testing" and bad:
            proposal = {"type": "rule_status", "rule": rule["id"], "value": "retired"}
            verdict = "Working the wrong way: propose retiring it"
        elif rule["status"] == "confirmed" and bad:
            proposal = {"type": "rule_status", "rule": rule["id"], "value": "testing"}
            verdict = "No longer holding up: propose moving it back to testing"
        elif z is None:
            verdict = f"Too few bets to judge ({a['n']} matched, {b['n']} not; want {MIN_N}+ each)"
        else:
            verdict = "No clear difference yet: keep watching"
        found.append({"id": f"rule:{rule['id']}", "area": "rule", "title": rule["name"], "verdict": verdict,
                      "matched": a, "rest": b, "gap": d, "z": z, "proposal": proposal})
    return found


def setting_findings(bets, settings, min_edge):
    found = []
    groups = [(name, stats([b["clv"] for b in bets if lo <= b["edge"] < hi])) for name, lo, hi in BUCKETS]
    low = groups[0][1]
    proposal, verdict = None, "Bets at every value level are beating the close, or there's too little data to say"
    if low["n"] >= MIN_N and low["se"] and low["avg"] < 0 and low["avg"] / low["se"] <= -Z and min_edge < 0.03:
        proposal = {"type": "setting", "rule": "min_edge", "key": "min", "value": 0.03}
        verdict = "Bets with only 2–3% value are losing to the close: propose raising the minimum to 3%"
    elif low["n"] < MIN_N:
        verdict = f"Too few 2–3% bets to judge yet ({low['n']}; want {MIN_N}+)"
    found.append({"id": "setting:min_edge", "area": "setting", "title": "Minimum value (now "
                  f"{min_edge:.0%})", "verdict": verdict, "groups": groups, "proposal": proposal})

    with_ctx = [b for b in bets if b["ctx"]]
    sharp = stats([b["clv"] for b in with_ctx if b["ctx"].get("sharp")])
    soft = stats([b["clv"] for b in with_ctx if not b["ctx"].get("sharp")])
    d, z = gap(sharp, soft)
    w = settings.get("sharp_weight", 0.0)
    proposal = None
    if z is not None and z >= Z and w < 0.75:
        proposal = {"type": "setting", "key": "sharp_weight", "value": round(w + 0.25, 2)}
        verdict = "Bets priced with Pinnacle beat the close clearly more often: propose leaning on it more"
    elif z is not None and z <= -Z and w > 0:
        proposal = {"type": "setting", "key": "sharp_weight", "value": round(max(0.0, w - 0.25), 2)}
        verdict = "Bets priced with Pinnacle do worse against the close: propose leaning on it less"
    elif z is None:
        verdict = f"Too few bets to compare ({sharp['n']} with Pinnacle, {soft['n']} without; want {MIN_N}+ each)"
    else:
        verdict = "No clear difference yet: keep the current weighting"
    found.append({"id": "setting:sharp_weight", "area": "setting", "title": f"Pinnacle weighting (now {w:.0%})",
                  "verdict": verdict, "matched": sharp, "rest": soft, "gap": d, "z": z, "proposal": proposal})
    return found


def claude_findings(con):
    try:
        rows = con.execute("SELECT verdict, clv FROM notes WHERE graded=1 AND clv IS NOT NULL").fetchall()
    except Exception:
        rows = []
    by = {v: stats([c for vv, c in rows if vv == v]) for v in ("clear", "caution", "skip")}
    skip, clear = by["skip"], by["clear"]
    d, z = gap(skip, clear)
    if z is None:
        verdict = (f"Too few of Claude's calls graded yet ({skip['n']} skips, {clear['n']} clears; "
                   f"want {MIN_N}+ each)")
    elif z <= -Z:
        verdict = "Claude's skip calls are saving money: the bets it flagged did worse against the close"
    elif z >= Z:
        verdict = ("Claude's skip calls are costing money: the bets it flagged beat the close more often. "
                   "Consider letting Add all include them")
    else:
        verdict = "No clear difference yet between the bets Claude flagged and the ones it cleared"
    return [{"id": "claude:skips", "area": "claude", "title": "Claude's news check", "verdict": verdict,
             "groups": [(v, s) for v, s in by.items()], "gap": d, "z": z, "proposal": None}]


def run(con, cfg):
    bets = load_bets(con)
    rules = cfg["rules"]
    min_edge = next((r["params"]["min"] for r in rules if r["id"] == "min_edge"), 0.02)
    overall = stats([b["clv"] for b in bets])
    findings = rule_findings(bets, rules) + setting_findings(bets, cfg["settings"], min_edge) + claude_findings(con)
    return {"generated": datetime.now().isoformat(timespec="seconds"), "bets": overall,
            "first": min((b["slate_date"] for b in bets), default=None),
            "last": max((b["slate_date"] for b in bets), default=None),
            "min_n": MIN_N, "findings": findings}


def markdown(rep):
    pct = lambda x: "—" if x is None else f"{x:+.1%}"
    b = rep["bets"]
    L = [f"# Weekly review · {rep['generated'][:10]}", "",
         f"{b['n']} graded bets ({rep['first']} to {rep['last']}) · average vs. the close {pct(b['avg'])}", "",
         "Judged by closing-line value, not wins. Nothing changes until you apply a proposal in the Rulebook.", ""]
    for f in rep["findings"]:
        L += [f"## {f['title']}", "", f["verdict"] + ".", ""]
        if f.get("proposal"):
            L += [f"Proposal: `{json.dumps(f['proposal'])}`", ""]
    return "\n".join(L)


def save(rep, out_dir=ROOT / "reports"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    day = rep["generated"][:10]
    (out / f"review-{day}.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    (out / f"review-{day}.md").write_text(markdown(rep), encoding="utf-8")
    return out / f"review-{day}.md"


if __name__ == "__main__":
    import sys

    from .db import DEFAULT_DB, connect
    from .grading import grade_bets, grade_notes
    from .notes import ensure_table

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--rules", default=str(ROOT / "rules.json"))
    a = ap.parse_args()
    cfg = json.loads(Path(a.rules).read_text(encoding="utf-8"))
    con = connect(a.db)
    ensure_table(con)
    grade_notes(con, cfg)
    grade_bets(con, cfg)
    rep = run(con, cfg)
    sys.stdout.reconfigure(encoding="utf-8")
    print(markdown(rep))
    print(f"\nSaved {save(rep)}")
