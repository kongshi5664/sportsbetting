"""Walk-forward backtest of the NFL spread model against the closing line.

    python -m tipoff.nfl_spreads.backtest                       # baseline: EPA ratings + HFA
    python -m tipoff.nfl_spreads.backtest --factors rest qb_change
    python -m tipoff.nfl_spreads.backtest --report-from 2015 --db data/nfl.db

Writes reports/nfl/spreads-<name>-<date>.md and .json (plus a CSV of every prediction), and
prints the headline table. Needs `python -m tipoff.nfl_spreads.load` first. No odds credits used.
"""
import argparse
from datetime import date

from ..backtest import reports_dir
from .data import connect_nfl, load_epa, load_games
from .harness import Config, evaluate, markdown, save, upcoming, walk_forward


def run(db=None, factor_names=(), report_from=2012, out_dir=None, quiet=False):
    con = connect_nfl(db)
    games, epa = load_games(con), load_epa(con)
    con.close()
    if games.empty or epa.empty:
        raise SystemExit("No NFL spread data: run python -m tipoff.nfl_spreads.load --seasons 2006-2026 first.")
    cfg = Config(report_from=report_from)
    r = walk_forward(games, epa, factor_names, cfg)
    rep = evaluate(r, cfg)
    up = upcoming(r)
    text = markdown(rep, up)
    stem = f"spreads-{r.name.replace('+', 'plus-').strip('-')}-{date.today():%Y-%m-%d}"
    out = out_dir or reports_dir("nfl")
    md = save(text, {**rep, "upcoming": up.to_dict("records") if len(up) else []}, out, stem)
    r.preds.to_csv(out / f"{stem}-predictions.csv", index=False)
    if not quiet:
        print(text)
        print(f"Saved {md}")
    return r, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="database (default data/nfl.db)")
    ap.add_argument("--factors", nargs="*", default=[], help="registered factors to add to the baseline")
    ap.add_argument("--report-from", type=int, default=2012, help="first season in the headline numbers")
    a = ap.parse_args(argv)
    run(a.db, a.factors, a.report_from)


if __name__ == "__main__":
    main()
