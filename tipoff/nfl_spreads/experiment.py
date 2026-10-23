"""Measure what a factor is worth: baseline vs baseline + factor(s), same walk-forward harness.

    python -m tipoff.nfl_spreads.experiment rest qb_change          # baseline, +rest, +qb_change, +both
    python -m tipoff.nfl_spreads.experiment qb_change --no-combined
    python -m tipoff.nfl_spreads.experiment --list                  # registered factors

Every variant is refitted per test season on earlier seasons only (factor coefficients included),
so a factor is never tuned on the seasons it is scored on. Prints a side-by-side table and writes
reports/nfl/experiment-<factors>-<date>.md and .json. Judge a factor by model MAE and by the blend's
cover log-loss against the market alone; ATS swings of a point or two are mostly noise (see the CIs).
"""
import argparse
from datetime import date

from ..backtest import reports_dir
from . import factors as factor_mod
from .data import connect_nfl, load_epa, load_games
from .harness import EDGE_TIERS, Config, evaluate, rating_cache, save, walk_forward


def variants(names, combined=True):
    out = [()] + [(n,) for n in names]
    if combined and len(names) > 1:
        out.append(tuple(names))
    return out


def compare(games, epa, names, cfg=Config(), combined=True):
    cache = rating_cache(games, epa, cfg.grid)
    reps = []
    for v in variants(names, combined):
        reps.append(evaluate(walk_forward(games, epa, v, cfg, cache=cache), cfg))
    return reps


def _avg_betas(rep):
    tot = {}
    for f in rep["fits"]:
        for k, v in f["betas"].items():
            tot.setdefault(k, []).append(v)
    return {k: sum(v) / len(v) for k, v in tot.items()}


def table(reps):
    base = reps[0]["overall"]
    rows = []
    hdr = ["variant", "games", "model MAE", "vs base", "market MAE", "blend-mkt logloss", "mean w",
           "ATS win%", "units"] + [f"tier {lab} (n, win%)" for _, _, lab in EDGE_TIERS] + \
          ["value bets (n, win%, units)", "avg coefficients (pts)"]
    for r in reps:
        o = r["overall"]
        cs = o["cover_scores"]
        vb = o["blend_value_bets"]
        rows.append([r["name"], str(o["games"]), f"{o['model_mae']:.3f}", f"{o['model_mae'] - base['model_mae']:+.3f}",
                     f"{o['market_mae']:.3f}", f"{cs['blend']['logloss'] - cs['market']['logloss']:+.5f}",
                     f"{cs['mean_w']:.2f}", f"{100 * o['ats_all']['win_pct']:.1f}%", f"{o['ats_all']['units']:+.1f}"] +
                    [f"{a['bets']}, {100 * a['win_pct']:.1f}%" if a["win_pct"] is not None else "0"
                     for a in o["edge_tiers"].values()] +
                    [f"{vb['bets']}, {100 * vb['win_pct']:.1f}%, {vb['units']:+.1f}" if vb["win_pct"] is not None else "0",
                     ", ".join(f"{k} {v:+.2f}" for k, v in _avg_betas(r).items()) or "-"])
    return hdr, rows


def markdown(reps, cfg):
    hdr, rows = table(reps)
    L = [f"# NFL spreads: factor experiment ({', '.join(reps[-1]['factors']) or 'baseline'})", "",
         f"Seasons {cfg.report_from}+ (walk-forward; each variant refitted on earlier seasons only). Judged against",
         "the closing spread. 'blend-mkt logloss' < 0 means blending the model into the close beat the close alone.", "",
         "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    L += ["| " + " | ".join(r) + " |" for r in rows]
    L += ["", "## Completed seasons only", "", "| variant | games | model MAE | market MAE | ATS win% | units |",
          "|---|---|---|---|---|---|"]
    for r in reps:
        c = r["completed_seasons"]
        L.append(f"| {r['name']} | {c['games']} | {c['model_mae']:.3f} | {c['market_mae']:.3f} | "
                 f"{100 * c['ats_all']['win_pct']:.1f}% | {c['ats_all']['units']:+.1f} |")
    L += ["", "## Model MAE by season", "", "| season | " + " | ".join(r["name"] for r in reps) + " | market |",
          "|" + "---|" * (len(reps) + 2)]
    for s in reps[0]["by_season"]:
        L.append(f"| {s} | " + " | ".join(f"{r['by_season'][s]['model_mae']:.2f}" for r in reps) +
                 f" | {reps[0]['by_season'][s]['market_mae']:.2f} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("factors", nargs="*", help="registered factor names")
    ap.add_argument("--db", help="database (default data/nfl.db)")
    ap.add_argument("--report-from", type=int, default=2012)
    ap.add_argument("--no-combined", action="store_true", help="skip the all-factors-together variant")
    ap.add_argument("--list", action="store_true", help="list registered factors")
    a = ap.parse_args(argv)
    if a.list or not a.factors:
        for f in factor_mod.REGISTRY.values():
            print(f"{f.name:12} {f.description}")
        return
    factor_mod.get(a.factors)
    con = connect_nfl(a.db)
    games, epa = load_games(con), load_epa(con)
    con.close()
    cfg = Config(report_from=a.report_from)
    reps = compare(games, epa, a.factors, cfg, combined=not a.no_combined)
    text = markdown(reps, cfg)
    print(text)
    md = save(text, {"variants": reps}, reports_dir("nfl"),
              f"experiment-{'-'.join(a.factors)}-{date.today():%Y-%m-%d}")
    print(f"Saved {md}")


if __name__ == "__main__":
    main()
