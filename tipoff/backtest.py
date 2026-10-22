"""Replay history through the pricing + rulebook and report what would have happened.

    python -m tipoff.backtest                 # uses data/tipoff.db and rules.json
    python -m tipoff.backtest --db data/sample.db
    python -m tipoff.backtest --league nfl    # data/nfl.db and rules.nfl.json; reports in reports/nfl/

For each game it uses only what was knowable at the 'bet' snapshot: odds at that moment
and box scores from earlier dates. It grades every bet on the result AND on closing-line
value (CLV), then tests each 'testing' rule on an earlier-seasons sample and on a held-out
latest season. Rules are never changed automatically; the report recommends, you decide.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .db import DEFAULT_DB, connect
from . import leagues
from .features import MARKET_STAT, FeatureStore
from .pricing import consensus, ev, kelly_stake, prob_over, to_american, to_decimal

ROOT = Path(__file__).resolve().parent.parent


# ---------- rule predicates: return True when the rule's condition matches a bet ----------

def _rule_matches(rule, b):
    p, f = rule.get("params", {}), b["f"]
    rid = rule["id"]
    if rid == "skip_early_season":
        return f["games_played"] < p.get("min_games", 8)
    if rid == "b2b_big_reb_over":
        return b["stat"] == "reb" and b["side"] == "Over" and f["b2b"] and f["season_reb"] >= p.get("min_season_reb", 8)
    if rid == "role_player_props":
        return f["season_pts"] < p.get("max_season_pts", 15)
    if rid == "minutes_spike":
        return b["side"] == "Over" and f["min_trend"] >= p.get("min_trend", 1.075)
    if rid == "model_disagrees":
        return b["p_model"] < 0.5
    if rid == "soft_matchup_over":
        return b["side"] == "Over" and f["opp_factor"] >= p.get("min_opp_factor", 1.03)
    raise KeyError(f"No predicate for rule '{rid}'. Add one to _rule_matches in backtest.py.")


# ---------- building candidate bets ----------

def _load_snapshot(con, event_id, label):
    lines = defaultdict(lambda: defaultdict(dict))  # (market, key, point) -> book -> side -> price
    names = {}
    for r in con.execute("SELECT * FROM prop_odds WHERE event_id=? AND label=?", (event_id, label)):
        k = (r["market"], r["name_key"], r["point"])
        lines[k][r["book"]][r["side"]] = r["price"]
        names[r["name_key"]] = r["player"]
    return lines, names


def build_candidates(con, fs, settings):
    targets = set(settings["target_books"])
    w = settings["model_weight"]
    sharp = dict(sharp=tuple(settings.get("sharp_books", ())), sharp_weight=settings.get("sharp_weight", 0.0))
    cands, calib = [], []
    events = con.execute("SELECT * FROM events ORDER BY commence_time").fetchall()
    for e in events:
        bet, names = _load_snapshot(con, e["event_id"], "bet")
        close, _ = _load_snapshot(con, e["event_id"], "close")
        date = e["game_date"]
        best_per_player_market = {}
        for (market, key, point), books in bet.items():
            stat = fs.league.market_stat.get(market)
            if not stat:
                continue
            others = {b: s for b, s in books.items() if b not in targets}
            p_mkt_over = consensus(others, **sharp) if others else consensus(books, **sharp)
            f = fs.player(key, date, stat)
            row = fs.game_row(key, date)
            if p_mkt_over is None or f is None or row is None or row[stat] is None:
                continue  # no fair price, no history, or he didn't play (bet voided)
            actual = row[stat]
            p_over, p_push = prob_over(point, f["proj"], f["sd"], stat)
            if actual != point:
                calib.append((p_mkt_over, p_over / max(1e-9, 1 - p_push), 1 if actual > point else 0))
            close_over = consensus({b: s for b, s in close.get((market, key, point), {}).items()
                                    if b not in targets}, **sharp) if (market, key, point) in close else None
            for side in ("Over", "Under"):
                offers = [(s[side], b) for b, s in books.items() if b in targets and side in s]
                if not offers:
                    continue
                price, book = max(offers, key=lambda o: to_decimal(o[0]))
                p_mkt = p_mkt_over if side == "Over" else 1 - p_mkt_over
                p_mod_raw = p_over if side == "Over" else 1 - p_over - p_push
                p_model = p_mod_raw / max(1e-9, 1 - p_push)
                fair = w * p_model + (1 - w) * p_mkt
                p_close = None if close_over is None else (close_over if side == "Over" else 1 - close_over)
                result = "push" if actual == point else ("win" if (actual > point) == (side == "Over") else "loss")
                c = {
                    "event_id": e["event_id"], "date": date, "season": row["season"],
                    "game": f"{e['away_team']} @ {e['home_team']}", "player": names.get(key, key), "key": key,
                    "market": market, "stat": stat, "side": side, "point": point, "price": price, "book": book,
                    "p_market": p_mkt, "p_model": p_model, "fair": fair, "edge": ev(fair, price),
                    "clv": None if p_close is None else ev(p_close, price),
                    "n_refs": sum(1 for s in others.values() if "Over" in s and "Under" in s),
                    "close_price": None if p_close is None else to_american(p_close),
                    "actual": actual, "result": result, "f": f,
                }
                pk = (key, market)
                if pk not in best_per_player_market or c["edge"] > best_per_player_market[pk]["edge"]:
                    best_per_player_market[pk] = c
        cands.extend(best_per_player_market.values())
    return cands, calib


# ---------- applying the rulebook ----------

def apply_card_rules(cands, rules):
    by_id = {r["id"]: r for r in rules}
    min_edge = by_id.get("min_edge", {}).get("params", {}).get("min", 0.02)
    per_player = by_id.get("max_per_player", {}).get("params", {}).get("max", 2)
    per_night = by_id.get("max_per_night", {}).get("params", {}).get("max", 12)
    confirmed_avoid = [r for r in rules if r["status"] == "confirmed" and r["kind"] == "avoid"]

    min_refs = by_id.get("min_ref_books", {}).get("params", {}).get("min", 1)
    pool = [c for c in cands if c["edge"] >= min_edge and c.get("n_refs", min_refs) >= min_refs
            and not any(_rule_matches(r, c) for r in confirmed_avoid)]
    nights = defaultdict(list)
    for c in pool:
        nights[c["date"]].append(c)
    card = []
    for date in sorted(nights):
        count = defaultdict(int)
        taken = 0
        for c in sorted(nights[date], key=lambda x: -x["edge"]):
            if taken >= per_night or count[c["key"]] >= per_player:
                continue
            count[c["key"]] += 1
            taken += 1
            card.append(c)
    return card


# ---------- metrics ----------

def metrics(bets):
    n = len(bets)
    units = sum((to_decimal(b["price"]) - 1) if b["result"] == "win" else (-1 if b["result"] == "loss" else 0) for b in bets)
    wins = sum(b["result"] == "win" for b in bets)
    losses = sum(b["result"] == "loss" for b in bets)
    clvs = [b["clv"] for b in bets if b["clv"] is not None]
    m = sum(clvs) / len(clvs) if clvs else None
    se = (math.sqrt(sum((x - m) ** 2 for x in clvs) / (len(clvs) - 1)) / math.sqrt(len(clvs))) if len(clvs) > 1 else None
    return {
        "n": n, "wins": wins, "losses": losses, "units": round(units, 2),
        "roi": round(units / n, 4) if n else None,
        "avg_clv": None if m is None else round(m, 4),
        "clv_ci95": None if se is None else [round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)],
        "beat_close": round(sum(x > 0 for x in clvs) / len(clvs), 3) if clvs else None,
        "avg_edge": round(sum(b["edge"] for b in bets) / n, 4) if n else None,
    }


def judge_rule(rule, pool, holdout):
    train = [b for b in pool if b["season"] != holdout]
    hold = [b for b in pool if b["season"] == holdout]
    out = {"id": rule["id"], "name": rule["name"], "kind": rule["kind"], "status": rule["status"]}
    split = {}
    for name, s in (("train", train), ("holdout", hold), ("all", pool)):
        m = [b for b in s if _rule_matches(rule, b)]
        r = [b for b in s if not _rule_matches(rule, b)]
        split[name] = {"matched": metrics(m), "rest": metrics(r)}
    out["results"] = split

    def gap(sp):  # matched CLV minus rest CLV
        a, b = split[sp]["matched"]["avg_clv"], split[sp]["rest"]["avg_clv"]
        return None if a is None or b is None else a - b

    g_tr, g_ho = gap("train"), gap("holdout")
    n_tr, n_ho = split["train"]["matched"]["n"], split["holdout"]["matched"]["n"]
    ci = split["all"]["matched"]["clv_ci95"]
    good_dir = (lambda g: g > 0) if rule["kind"] == "prefer" else (lambda g: g < 0)
    if n_tr < 50 or n_ho < 30 or g_tr is None or g_ho is None:
        verdict, why = "keep testing", f"Not enough matched bets yet ({n_tr} earlier, {n_ho} holdout; want 50 and 30)."
    elif good_dir(g_tr) and good_dir(g_ho) and (
            (rule["kind"] == "prefer" and ci and ci[0] > 0) or (rule["kind"] == "avoid" and ci and ci[1] < 0.01)):
        verdict, why = "promote", f"Held up in both samples (CLV gap {g_tr:+.1%} earlier, {g_ho:+.1%} holdout)."
    elif not good_dir(g_tr) and not good_dir(g_ho):
        verdict, why = "retire", f"Wrong direction in both samples (CLV gap {g_tr:+.1%} earlier, {g_ho:+.1%} holdout)."
    else:
        verdict, why = "keep testing", f"Mixed: CLV gap {g_tr:+.1%} earlier, {g_ho:+.1%} holdout."
    out["verdict"], out["why"] = verdict, why
    return out


def brier(pairs, idx):
    return sum((p[idx] - p[2]) ** 2 for p in pairs) / len(pairs) if pairs else None


# ---------- report ----------

def pct(x):
    return "—" if x is None else f"{x:+.1%}"


def reports_dir(league=None):
    """NBA reports stay in reports/; other leagues get their own folder so they never mix."""
    lg = leagues.get(league)
    return ROOT / "reports" if lg.id == "nba" else ROOT / "reports" / lg.id


def run(db_path, rules_path, out_dir, league=None):
    cfg = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    settings, rules = cfg["settings"], cfg["rules"]
    con = connect(db_path, league=league)
    fs = FeatureStore(con, league)
    cands, calib = build_candidates(con, fs, settings)
    if not cands:
        raise SystemExit("No gradable lines found. Run the backfills first (or tipoff.sample_data).")
    seasons = sorted({c["season"] for c in cands})
    holdout = seasons[-1] if settings.get("holdout_season", "latest") == "latest" else settings["holdout_season"]
    card = apply_card_rules(cands, rules)

    # bankroll simulation with fractional Kelly on the card
    # All of a night's bets are sized from that night's opening bankroll, then scaled down
    # together if they'd risk more than nightly_risk_cap of it.
    bank = start = settings["bankroll"]
    cap = settings.get("nightly_risk_cap", 0.08)
    ledger, nights, i = [], defaultdict(list), 0
    for b in card:
        nights[b["date"]].append(b)
    for date in sorted(nights):
        bets = sorted(nights[date], key=lambda x: -x["edge"])
        stakes = [kelly_stake(b["fair"], b["price"], bank, settings["kelly_fraction"], settings["stake_cap_units"]) for b in bets]
        total = sum(stakes)
        if total > cap * bank:
            stakes = [s * cap * bank / total for s in stakes]
        night_pnl = 0
        for b, stake in zip(bets, stakes):
            i += 1
            pnl = stake * (to_decimal(b["price"]) - 1) if b["result"] == "win" else (-stake if b["result"] == "loss" else 0)
            night_pnl += pnl
            ledger.append({
                "i": i, "date": b["date"], "game": b["game"], "bet": f"{b['player']} {b['side'][0].lower()}{b['point']:g} {b['stat']}",
                "book": b["book"], "took": b["price"], "close": b["close_price"], "clv": b["clv"], "edge": round(b["edge"], 4),
                "result": b["result"], "actual": b["actual"], "stake": round(stake, 2), "pnl": round(pnl, 2),
            })
        bank += night_pnl
        ledger[-1]["bankroll_after_night"] = round(bank, 2)

    overall = metrics(card)
    by_market = {mk: metrics([b for b in card if b["market"] == mk]) for mk in sorted({b["market"] for b in card})}
    buckets = {"2-4%": (0.02, 0.04), "4-6%": (0.04, 0.06), "6-10%": (0.06, 0.10), "10%+": (0.10, 9)}
    by_edge = {k: metrics([b for b in card if lo <= b["edge"] < hi]) for k, (lo, hi) in buckets.items()}
    by_season = {s: metrics([b for b in card if b["season"] == s]) for s in seasons}
    testing = [r for r in rules if r["status"] == "testing"]
    judged = [judge_rule(r, card, holdout) for r in testing]
    b_mkt, b_mod = brier(calib, 0), brier(calib, 1)
    blend = settings["model_weight"]
    b_blend = (sum(((1 - blend) * p[0] + blend * p[1] - p[2]) ** 2 for p in calib) / len(calib)) if calib else None

    report = {
        "generated": datetime.now().isoformat(timespec="seconds"), "db": str(db_path),
        "settings": settings, "seasons": seasons, "holdout": holdout,
        "lines_evaluated": len(calib), "candidates": len(cands),
        "overall": overall, "by_season": by_season, "by_market": by_market, "by_edge": by_edge,
        "bankroll": {"start": start, "end": round(bank, 2)},
        "calibration": {"brier_market": b_mkt, "brier_model": b_mod, "brier_blend": b_blend},
        "rules": judged,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (out_dir / f"backtest-{stamp}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out_dir / "ledger.json").write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
    md = render_md(report)
    (out_dir / f"backtest-{stamp}.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nSaved {out_dir / f'backtest-{stamp}.md'} and {out_dir / 'ledger.json'}")
    return report


def render_md(r):
    o = r["overall"]
    L = [f"# Backtest — {', '.join(r['seasons'])} (holdout: {r['holdout']})", "",
         f"{r['lines_evaluated']:,} graded prop lines · {r['candidates']:,} candidates · **{o['n']:,} bets on the card**", "",
         "## Headline", "",
         f"- Record {o['wins']}–{o['losses']} · {o['units']:+.1f} units flat · ROI {pct(o['roi'])}",
         f"- Average CLV **{pct(o['avg_clv'])}** (95% range {pct(o['clv_ci95'][0]) if o['clv_ci95'] else '—'} to {pct(o['clv_ci95'][1]) if o['clv_ci95'] else '—'}) · beat the close on {o['beat_close']:.0%} of bets" if o["avg_clv"] is not None else "- No closing lines to grade CLV.",
         f"- Estimated edge on the card averaged {pct(o['avg_edge'])} vs. {pct(o['avg_clv'])} realized CLV. "
         "Picking the best few of many lines favors overestimates, so treat CLV as the real edge.",
         f"- Bankroll ${r['bankroll']['start']:,} → ${r['bankroll']['end']:,.0f} at {r['settings']['kelly_fraction']} Kelly",
         "", "CLV is the number to trust. Results over a few hundred bets are mostly luck; CLV shows whether the prices were good.", ""]
    c = r["calibration"]
    if c["brier_market"] is not None:
        better = c["brier_model"] < c["brier_market"]
        L += ["## Is our projection adding anything?", "",
              f"Brier score on every graded line (lower is better): market **{c['brier_market']:.4f}**, "
              f"our model **{c['brier_model']:.4f}**, blend **{c['brier_blend']:.4f}**.", "",
              ("The model beats the market on its own. Consider raising model_weight." if better else
               "The market is more accurate than our model. Keep model_weight low; the edge has to come from price differences, not predictions."),
              ""]
    def table(title, d):
        rows = [f"## {title}", "", "| | Bets | Record | Units | ROI | Avg CLV | Beat close |", "|---|---|---|---|---|---|---|"]
        for k, m in d.items():
            if m["n"]:
                bc = "—" if m["beat_close"] is None else "{:.0%}".format(m["beat_close"])
                rows.append(f"| {k} | {m['n']} | {m['wins']}–{m['losses']} | {m['units']:+.1f} | {pct(m['roi'])} | {pct(m['avg_clv'])} | {bc} |")
        return rows + [""]
    L += table("By season", r["by_season"]) + table("By market", r["by_market"]) + table("By edge size", r["by_edge"])
    L += ["If bigger estimated edges don't produce bigger CLV, the edge estimate isn't trustworthy yet.", "",
          "## Testing rules", "", "| Rule | Kind | Matched bets | Matched CLV | Others' CLV | Recommendation |", "|---|---|---|---|---|---|"]
    for j in r["rules"]:
        a = j["results"]["all"]
        L.append(f"| {j['name']} | {j['kind']} | {a['matched']['n']} | {pct(a['matched']['avg_clv'])} | {pct(a['rest']['avg_clv'])} | **{j['verdict']}** — {j['why']} |")
    L += ["", "Recommendations only. Edit rules.json to change a status."]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="default: the league's database")
    ap.add_argument("--rules", default=None, help="default: the league's rules file")
    ap.add_argument("--out", default=None, help="default: reports/ (NBA) or reports/<league>/")
    leagues.add_argument(ap)
    a = ap.parse_args()
    lg = leagues.get(a.league)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    run(a.db or (str(DEFAULT_DB) if lg.id == "nba" else str(lg.db_path)), a.rules or str(lg.rules_path),
        a.out or str(reports_dir(lg)), lg)
