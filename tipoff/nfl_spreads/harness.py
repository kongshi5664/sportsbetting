"""Walk-forward backtest for the NFL spread model, judged against the closing spread.

For each test season S:
  * every fitted thing uses seasons < S only: the rating parameters (chosen from a small grid by
    training-season fit), the margin model (scale, per-season HFA, factor coefficients), the
    cover/push distribution, and the model-vs-market blend weight (chosen on earlier seasons'
    out-of-sample predictions);
  * every game in S is predicted from ratings built from games before its date (ratings.py) and
    factor features that only see earlier games (factors.py).

Evaluation is against nflverse's closing spread, the hardest test there is: real bets would be
placed earlier at Hard Rock, where lines are softer, but we only have closers historically. A model
that cannot beat the close on direction can still be useful early in the week; one that beats
the close is rare.
"""
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import factors as factor_mod
from .cover import CoverModel, no_push_prob
from .model import fit
from .ratings import DEFAULT_GRID, pregame_ratings, rating_diff

BREAK_EVEN = 110 / 210          # win rate needed at -110
WIN_UNITS = 100 / 110
EDGE_TIERS = ((0.0, 1.5, "<1.5"), (1.5, 2.5, "1.5-2.5"), (2.5, 4.0, "2.5-4"), (4.0, math.inf, "4+"))
PROB_TIERS = ((0.0, BREAK_EVEN, "<52.4%"), (BREAK_EVEN, 0.54, "52.4-54%"), (0.54, 0.56, "54-56%"),
              (0.56, 1.01, "56%+"))
BASE_COLS = ("game_id", "season", "game_type", "week", "gameday", "home_team", "away_team", "location",
             "result", "spread_line", "home_qb_name", "away_qb_name")


@dataclass
class Config:
    first_test: int = 2008       # first season predicted out of sample (feeds the blend weight)
    report_from: int = 2012      # first season in the headline numbers
    train_start: int = 2007      # 2006 is the ratings' burn-in (no prior season)
    grid: tuple = DEFAULT_GRID
    hfa_seasons: int = 3
    blend_grid: tuple = tuple(round(x, 2) for x in np.arange(0, 1.0001, 0.05))
    min_blend_rows: int = 200


@dataclass
class Run:
    name: str
    factors: tuple
    preds: pd.DataFrame
    fits: list = field(default_factory=list)


def rating_cache(games, epa, grid=DEFAULT_GRID):
    """{RatingParams: Series(game_id -> home minus away net rating)} for every grid point."""
    return {p: rating_diff(pregame_ratings(games, epa, p)) for p in grid}


def _logloss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y):
    return float(np.mean((p - y) ** 2))


def _cover_target(df):
    """Rows with a result and a line that weren't pushes, and y = home covered."""
    d = df[df["result"].notna() & df["spread_line"].notna() & (df["result"] != df["spread_line"])]
    return d, (d["result"] > d["spread_line"]).to_numpy(dtype=float)


def choose_blend(prior: pd.DataFrame, cover: CoverModel, grid):
    """Blend weight w (fair margin = w*model + (1-w)*close) with the lowest cover log-loss on
    earlier seasons' out-of-sample predictions."""
    d, y = _cover_target(prior)
    m, line = d["pred"].to_numpy(), d["spread_line"].to_numpy()
    best = (None, math.inf)
    for w in grid:
        pc, pp = cover.probs(w * m + (1 - w) * line, line)
        ll = _logloss(no_push_prob(pc, pp), y)
        if ll < best[1] - 1e-12:
            best = (w, ll)
    return best[0]


def walk_forward(games: pd.DataFrame, epa: pd.DataFrame, factor_names=(), cfg: Config = Config(),
                 cache=None, name=None) -> Run:
    games = games.sort_values(["gameday", "game_id"]).reset_index(drop=True)
    facs = factor_mod.get(list(factor_names))
    feats = factor_mod.compute(games, facs) if facs else pd.DataFrame(index=games["game_id"])
    fcols = list(feats.columns)
    diffs = cache if cache is not None else rating_cache(games, epa, cfg.grid)
    base = games[list(BASE_COLS)].set_index("game_id", drop=False).join(feats)
    ids = base.index
    seasons = sorted(base["season"].unique())
    out, fits = [], []
    for S in [s for s in seasons if s >= cfg.first_test]:
        train_mask = ((base["season"] >= cfg.train_start) & (base["season"] < S) & base["result"].notna()).to_numpy()
        test_mask = (base["season"] == S).to_numpy()
        if not train_mask.any() or not test_mask.any():
            continue
        best = None
        for p, d in diffs.items():
            tr = base[train_mask].assign(diff=d.reindex(ids[train_mask]).to_numpy())
            mdl = fit(tr, fcols, cfg.hfa_seasons)
            if best is None or mdl.sse < best[1].sse:
                best = (p, mdl, tr)
        params, mdl, tr = best
        assert max(mdl.train_seasons) < S, "walk-forward must never fit on the test season"
        cover = CoverModel(tr["result"].to_numpy() - mdl.fitted, tr["result"].to_numpy(), mdl.fitted)
        test = base[test_mask].assign(diff=diffs[params].reindex(ids[test_mask]).to_numpy())
        pred = mdl.predict(test)
        prior = pd.concat(out) if out else pd.DataFrame(columns=["result", "spread_line", "pred"])
        prior = prior[prior["season"] < S] if len(prior) else prior
        w = choose_blend(prior, cover, cfg.blend_grid) if len(_cover_target(prior)[0]) >= cfg.min_blend_rows else 0.0
        line = test["spread_line"].to_numpy(dtype=float)
        has_line = np.isfinite(line)
        safe_line = np.where(has_line, line, np.round(pred))
        pc, pp = cover.probs(pred, safe_line)
        blend = w * pred + (1 - w) * safe_line
        bc, bp = cover.probs(blend, safe_line)
        mc, mp = cover.probs(safe_line, safe_line)
        rows = test.copy()
        rows["pred"] = pred
        rows["edge"] = np.where(has_line, pred - line, np.nan)
        rows["p_cover"], rows["p_push"] = np.where(has_line, pc, np.nan), np.where(has_line, pp, np.nan)
        rows["blend_w"] = w
        rows["blend_margin"] = np.where(has_line, blend, np.nan)
        rows["blend_cover"], rows["blend_push"] = np.where(has_line, bc, np.nan), np.where(has_line, bp, np.nan)
        rows["market_cover"], rows["market_push"] = np.where(has_line, mc, np.nan), np.where(has_line, mp, np.nan)
        out.append(rows.reset_index(drop=True))
        fits.append({"season": int(S), "train_seasons": [min(mdl.train_seasons), max(mdl.train_seasons)],
                     "n_train": mdl.n, "rating_params": params.label(), "scale": round(mdl.scale, 2),
                     "hfa": round(mdl.hfa, 2), "season_hfa_last3": {k: round(v, 2) for k, v in
                                                                     list(mdl.season_hfa.items())[-3:]},
                     "betas": {k: round(v, 3) for k, v in mdl.betas.items()}, "blend_w": w,
                     "cover": cover.describe()})
    preds = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    return Run(name or ("baseline" if not factor_names else "+" + "+".join(factor_names)),
               tuple(factor_names), preds, fits)


# ------------------------------------------------------------------ evaluation

def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(c - h, 4), round(c + h, 4))


def ats(df: pd.DataFrame, side: np.ndarray) -> dict:
    """ATS record at -110 for bets on `side` (+1 home, -1 away, 0 no bet)."""
    res, line = df["result"].to_numpy(dtype=float), df["spread_line"].to_numpy(dtype=float)
    bet = side != 0
    win = bet & (((side > 0) & (res > line)) | ((side < 0) & (res < line)))
    push = bet & (res == line)
    loss = bet & ~win & ~push
    w, l, p = int(win.sum()), int(loss.sum()), int(push.sum())
    n = w + l
    units = w * WIN_UNITS - l
    return {"bets": int(bet.sum()), "w": w, "l": l, "p": p,
            "win_pct": round(w / n, 4) if n else None, "ci95": wilson(w, n),
            "units": round(units, 2), "roi": round(units / (n + p), 4) if n + p else None}


def graded(preds):
    return preds[preds["result"].notna() & preds["spread_line"].notna()]


def summarize(preds: pd.DataFrame) -> dict:
    d = graded(preds)
    if d.empty:
        return {"games": 0}
    res, line, pred = (d[c].to_numpy(dtype=float) for c in ("result", "spread_line", "pred"))
    edge = pred - line
    side = np.sign(edge)
    out = {"games": int(len(d)),
           "model_mae": round(float(np.mean(np.abs(res - pred))), 3),
           "market_mae": round(float(np.mean(np.abs(res - line))), 3),
           "model_rmse": round(float(np.sqrt(np.mean((res - pred) ** 2))), 3),
           "market_rmse": round(float(np.sqrt(np.mean((res - line) ** 2))), 3),
           "mean_abs_edge": round(float(np.mean(np.abs(edge))), 2),
           "ats_all": ats(d, side)}
    out["edge_tiers"] = {}
    for lo, hi, lab in EDGE_TIERS:
        m = (np.abs(edge) >= lo) & (np.abs(edge) < hi)
        out["edge_tiers"][lab] = ats(d, np.where(m, side, 0))
    p_home = no_push_prob(d["p_cover"].to_numpy(), d["p_push"].to_numpy())
    p_side = np.where(side > 0, p_home, 1 - p_home)
    out["prob_tiers"] = {}
    for lo, hi, lab in PROB_TIERS:
        m = (p_side >= lo) & (p_side < hi)
        out["prob_tiers"][lab] = ats(d, np.where(m, side, 0))
    # price-not-picks: bet only when the BLENDED fair chance beats -110's break-even
    b_home = no_push_prob(d["blend_cover"].to_numpy(), d["blend_push"].to_numpy())
    b_side = np.where(b_home >= 0.5, 1, -1)
    b_p = np.where(b_side > 0, b_home, 1 - b_home)
    out["blend_value_bets"] = ats(d, np.where(b_p > BREAK_EVEN, b_side, 0))
    t, y = _cover_target(d)
    k = d.index.get_indexer(t.index)
    mk = no_push_prob(d["market_cover"].to_numpy(), d["market_push"].to_numpy())[k]
    md = p_home[k]
    bl = b_home[k]
    out["cover_scores"] = {
        "n": int(len(y)),
        "market": {"logloss": round(_logloss(mk, y), 5), "brier": round(_brier(mk, y), 5)},
        "blend": {"logloss": round(_logloss(bl, y), 5), "brier": round(_brier(bl, y), 5)},
        "model_only": {"logloss": round(_logloss(md, y), 5), "brier": round(_brier(md, y), 5)},
        "mean_w": round(float(d["blend_w"].mean()), 3)}
    pushes = d[d["result"] == d["spread_line"]]
    whole = d[d["spread_line"] % 1 == 0]
    out["push_check"] = {"whole_number_lines": int(len(whole)), "pushes": int(len(pushes)),
                         "predicted_pushes": round(float(whole["market_push"].sum()), 1)}
    return out


def evaluate(run: Run, cfg: Config = Config()) -> dict:
    p = run.preds.reset_index(drop=True)
    p = p[p["season"] >= cfg.report_from]
    seasons = sorted(p["season"].unique())
    done = [s for s in seasons if graded(p[p["season"] == s]).shape[0] and
            p[(p["season"] == s)]["result"].notna().all()]
    rep = {"name": run.name, "factors": list(run.factors),
           "overall": summarize(p),
           "completed_seasons": summarize(p[p["season"].isin(done)]),
           "by_season": {int(s): summarize(p[p["season"] == s]) for s in seasons},
           "fits": [f for f in run.fits if f["season"] >= cfg.report_from]}
    if len(done) >= 6:
        mid = done[len(done) // 2]
        rep["early_half"] = summarize(p[p["season"].isin([s for s in done if s < mid])])
        rep["late_half"] = summarize(p[p["season"].isin([s for s in done if s >= mid])])
        rep["halves"] = [f"{done[0]}-{mid - 1}", f"{mid}-{done[-1]}"]
    return rep


def upcoming(run: Run) -> pd.DataFrame:
    """Unplayed games of the latest season that have a line: fair spread, edge and tier."""
    p = run.preds
    if p.empty:
        return p
    u = p[(p["season"] == p["season"].max()) & p["result"].isna() & p["spread_line"].notna()].copy()
    if u.empty:
        return u
    u["tier"] = [next(lab for lo, hi, lab in EDGE_TIERS if lo <= abs(e) < hi) for e in u["edge"]]
    b_home = no_push_prob(u["blend_cover"].to_numpy(), u["blend_push"].to_numpy())
    u["side"] = np.where(u["edge"] > 0, u["home_team"], u["away_team"])
    u["p_side_model"] = np.where(u["edge"] > 0, no_push_prob(u["p_cover"], u["p_push"]),
                                 1 - no_push_prob(u["p_cover"], u["p_push"]))
    u["p_side_blend"] = np.where(u["edge"] > 0, b_home, 1 - b_home)
    return u.sort_values(["gameday", "game_id"])


# ------------------------------------------------------------------ reports

def _pct(x):
    return "-" if x is None else f"{100 * x:.1f}%"


def _ci(c):
    return "-" if c[0] is None else f"{100 * c[0]:.1f}-{100 * c[1]:.1f}%"


def ats_line(a):
    return (f"{a['bets']} | {a['w']}-{a['l']}-{a['p']} | {_pct(a['win_pct'])} | {_ci(a['ci95'])} | "
            f"{a['units']:+.1f} | {_pct(a['roi']) if a['roi'] is not None else '-'}")


def markdown(rep: dict, up: pd.DataFrame = None, title="NFL spreads: walk-forward backtest") -> str:
    o, c = rep["overall"], rep["completed_seasons"]
    L = [f"# {title} ({rep['name']})", "",
         f"Generated {datetime.now():%Y-%m-%d %H:%M}. Factors: {', '.join(rep['factors']) or 'none (baseline)'}.", "",
         "Judged against nflverse's **closing** spread: the hardest test. Real bets would be placed earlier at",
         "Hard Rock, but only closers exist historically. Break-even at -110 is 52.38%. Fair spread = predicted",
         "home margin; spread_line is the market's expected home margin (+ = home favoured).", "",
         "## Accuracy by season", "",
         "| season | games | model MAE | market MAE | ATS all (W-L-P) | win% | units | blend w | blend logloss | market logloss |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in rep["by_season"].items():
        if not r.get("games"):
            continue
        a, cs = r["ats_all"], r["cover_scores"]
        L.append(f"| {s} | {r['games']} | {r['model_mae']:.2f} | {r['market_mae']:.2f} | {a['w']}-{a['l']}-{a['p']} | "
                 f"{_pct(a['win_pct'])} | {a['units']:+.1f} | {cs['mean_w']:.2f} | {cs['blend']['logloss']:.4f} | "
                 f"{cs['market']['logloss']:.4f} |")
    for lab, r in (("all reported", o), ("completed seasons", c)):
        if r.get("games"):
            a = r["ats_all"]
            L.append(f"| **{lab}** | {r['games']} | {r['model_mae']:.2f} | {r['market_mae']:.2f} | "
                     f"{a['w']}-{a['l']}-{a['p']} | {_pct(a['win_pct'])} | {a['units']:+.1f} | "
                     f"{r['cover_scores']['mean_w']:.2f} | {r['cover_scores']['blend']['logloss']:.4f} | "
                     f"{r['cover_scores']['market']['logloss']:.4f} |")
    L += ["", "## ATS by edge tier (|model fair - close|, all reported seasons)", "",
          "| tier (pts) | bets | W-L-P | win% | 95% CI | units | ROI |", "|---|---|---|---|---|---|---|"]
    L += [f"| {k} | {ats_line(a)} |" for k, a in o["edge_tiers"].items()]
    L += ["", "## ATS by model P(cover) of the side taken (pushes excluded)", "",
          "| P(cover) | bets | W-L-P | win% | 95% CI | units | ROI |", "|---|---|---|---|---|---|---|"]
    L += [f"| {k} | {ats_line(a)} |" for k, a in o["prob_tiers"].items()]
    cs = o["cover_scores"]
    L += ["", "## Blend: fair = w x model + (1 - w) x close (w picked on earlier seasons only)", "",
          f"Cover log-loss over {cs['n']} non-push games (lower is better): market {cs['market']['logloss']:.5f}, "
          f"blend {cs['blend']['logloss']:.5f}, model alone {cs['model_only']['logloss']:.5f}. "
          f"Brier: market {cs['market']['brier']:.5f}, blend {cs['blend']['brier']:.5f}, "
          f"model alone {cs['model_only']['brier']:.5f}. Mean w {cs['mean_w']:.2f}.", "",
          f"Value bets by the blended fair price (> 52.38% at -110): {ats_line(o['blend_value_bets'])} "
          "(bets | W-L-P | win% | CI | units | ROI).", ""]
    if "early_half" in rep:
        L += ["## Stability: completed seasons split in half", "",
              "| half | games | model MAE | market MAE | ATS win% | units | 4+ tier | blend vs market logloss |",
              "|---|---|---|---|---|---|---|---|"]
        for lab, r in zip(rep["halves"], (rep["early_half"], rep["late_half"])):
            t = r["edge_tiers"]["4+"]
            L.append(f"| {lab} | {r['games']} | {r['model_mae']:.2f} | {r['market_mae']:.2f} | "
                     f"{_pct(r['ats_all']['win_pct'])} | {r['ats_all']['units']:+.1f} | "
                     f"{t['w']}-{t['l']}-{t['p']} {_pct(t['win_pct'])} | "
                     f"{r['cover_scores']['blend']['logloss'] - r['cover_scores']['market']['logloss']:+.5f} |")
        L.append("")
    pc = o["push_check"]
    L += ["## Push check", "",
          f"Whole-number closing lines: {pc['whole_number_lines']}; actual pushes {pc['pushes']}, "
          f"predicted by the cover model at the market margin {pc['predicted_pushes']}.", "",
          "## Fits per test season (training seasons only)", "",
          "| season | trained on | rating params | scale | HFA | betas | blend w | cover model |",
          "|---|---|---|---|---|---|---|---|"]
    for f in rep["fits"]:
        L.append(f"| {f['season']} | {f['train_seasons'][0]}-{f['train_seasons'][1]} ({f['n_train']}) | "
                 f"{f['rating_params']} | {f['scale']} | {f['hfa']} | "
                 f"{', '.join(f'{k} {v:+.2f}' for k, v in f['betas'].items()) or '-'} | {f['blend_w']} | "
                 f"{f['cover']['kind']}, sd {f['cover']['sd']} |")
    if up is not None and len(up):
        L += ["", "## Upcoming games (latest nflverse line, not Hard Rock: check the real price first)", "",
              "| date | game | line (home) | fair (home) | edge | tier | side | P(side) model | P(side) blend |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in up.itertuples(index=False):
            L.append(f"| {r.gameday} | {r.away_team} @ {r.home_team} | {r.spread_line:+.1f} | {r.pred:+.1f} | "
                     f"{r.edge:+.1f} | {r.tier} | {r.side} | {_pct(r.p_side_model)} | {_pct(r.p_side_blend)} |")
    return "\n".join(L) + "\n"


def save(text: str, data: dict, out_dir: Path, stem: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"{stem}.md"
    md.write_text(text, encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return md
