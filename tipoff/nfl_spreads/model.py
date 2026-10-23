"""Margin model: predicted home margin = HFA + scale x (home net rating - away net rating) + factor terms.

Fitted by least squares on TRAINING seasons only. Home-field advantage has shrunk over the years
(roughly 3 points in the late 2000s, closer to 1.5 lately), so the fit gives every training season
its own HFA term and the prediction uses the average of the last `hfa_seasons` training seasons.
Neutral-site games get no HFA. The rating scale and each factor's coefficient are shared across
seasons.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class MarginModel:
    scale: float
    hfa: float
    betas: dict = field(default_factory=dict)
    season_hfa: dict = field(default_factory=dict)
    train_seasons: tuple = ()
    sse: float = 0.0
    n: int = 0
    fitted: np.ndarray = None     # in-sample predictions on the training rows (for the cover model)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        home = (df["location"] != "Neutral").to_numpy(dtype=float)
        m = self.hfa * home + self.scale * df["diff"].to_numpy(dtype=float)
        for c, b in self.betas.items():
            m = m + b * df[c].to_numpy(dtype=float)
        return m


def fit(train: pd.DataFrame, factor_cols=(), hfa_seasons=3) -> MarginModel:
    """train: rows with result, diff, location, season and the factor columns."""
    seasons = sorted(train["season"].unique())
    home = (train["location"] != "Neutral").to_numpy(dtype=float)
    cols = [np.where(train["season"].to_numpy() == s, home, 0.0) for s in seasons]
    cols.append(train["diff"].to_numpy(dtype=float))
    cols += [train[c].to_numpy(dtype=float) for c in factor_cols]
    X = np.column_stack(cols)
    y = train["result"].to_numpy(dtype=float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    s_hfa = {int(s): float(coef[i]) for i, s in enumerate(seasons)}
    recent = seasons[-hfa_seasons:]
    ns = len(seasons)
    return MarginModel(scale=float(coef[ns]), hfa=float(np.mean([s_hfa[int(s)] for s in recent])),
                       betas={c: float(coef[ns + 1 + i]) for i, c in enumerate(factor_cols)},
                       season_hfa=s_hfa, train_seasons=tuple(int(s) for s in seasons),
                       sse=float(resid @ resid), n=len(y), fitted=X @ coef)
