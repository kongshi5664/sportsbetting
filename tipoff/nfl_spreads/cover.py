"""P(cover) and P(push) for a predicted home margin against a spread, with NFL key numbers.

NFL margins pile up on 3, 7, 10, 6, 14 and almost never land on 0, so a smooth curve misprices
whole-number spreads. This model is built from TRAINING games only:

1. Base shape: the empirical distribution of residuals (actual margin - predicted margin),
   smoothed with a small Gaussian kernel so it has a CDF G. Base chance that the margin is the
   integer k given prediction m: G(k + 0.5 - m) - G(k - 0.5 - m).
2. Key numbers: for every |k|, compare how often training margins actually landed on |k| with
   how often the base shape expected them to (summed over the training games' own predictions).
   The ratio, shrunk toward 1, multiplies the base: 3 and 7 go up, 0 goes almost to nothing.
3. Normalise. P(home covers L) = P(margin > L); P(push) = P(margin == L) for whole-number L.

Fallback (documented): with fewer than `min_n` training residuals, a normal with sd 13.5 and no
key-number multipliers.
"""
import math

import numpy as np

K = np.arange(-80, 81)
FALLBACK_SD = 13.5


_erf = np.vectorize(math.erf)


def _norm_cdf(x):
    return 0.5 * (1.0 + _erf(np.asarray(x, dtype=float) / math.sqrt(2.0)))


class CoverModel:
    def __init__(self, residuals, margins=None, preds=None, shrink=10.0, min_n=300, bandwidth=None):
        e = np.asarray(residuals, dtype=float)
        e = e[np.isfinite(e)]
        self.n = len(e)
        self.grid = np.arange(-130.0, 130.0001, 0.05)
        if self.n < min_n:
            self.kind = "normal(sd=13.5) fallback"
            self.sd = FALLBACK_SD
            self.cdf_grid = _norm_cdf(self.grid / FALLBACK_SD)
            self.mult = np.ones(len(K))
            return
        self.kind = "empirical residuals + key numbers"
        self.sd = float(e.std())
        h = bandwidth or max(1.0, 1.06 * self.sd * self.n ** -0.2)
        self.bandwidth = h
        # Kernel CDF on the grid: mean over residuals of Phi((x - e_i) / h), via a fine histogram.
        bins = np.arange(-130.0, 130.0001, 0.05)
        hist, edges = np.histogram(e, bins=np.append(bins - 0.025, bins[-1] + 0.025))
        centers = (edges[:-1] + edges[1:]) / 2
        steps = np.arange(-math.ceil(6 * h / 0.05), math.ceil(6 * h / 0.05) + 1) * 0.05
        kern = np.diff(_norm_cdf(np.append(steps - 0.025, steps[-1] + 0.025) / h))
        dens = np.convolve(hist.astype(float), kern / kern.sum(), mode="same")
        self.cdf_grid = np.clip(np.cumsum(dens) / dens.sum(), 0.0, 1.0)
        self.grid = centers + 0.025
        self.mult = np.ones(len(K))
        if margins is not None and preds is not None:
            m = np.asarray(preds, dtype=float)
            y = np.rint(np.asarray(margins, dtype=float)).astype(int)
            base = self._base(m)                            # (n, |K|)
            exp_abs = np.zeros(81)
            obs_abs = np.zeros(81)
            np.add.at(exp_abs, np.abs(K), base.sum(axis=0))
            np.add.at(obs_abs, np.clip(np.abs(y), 0, 80), 1.0)
            ratio = (obs_abs + shrink) / (exp_abs + shrink)
            self.mult = ratio[np.abs(K)]
            self.key_ratio = {int(k): float(ratio[k]) for k in range(0, 15)}

    def _cdf(self, x):
        return np.interp(x, self.grid, self.cdf_grid, left=0.0, right=1.0)

    def _base(self, m):
        m = np.atleast_1d(np.asarray(m, dtype=float))[:, None]
        return self._cdf(K + 0.5 - m) - self._cdf(K - 0.5 - m)

    def pmf(self, m):
        """(n, len(K)) probabilities of each whole-number home margin K given predictions m."""
        p = self._base(m) * self.mult
        return p / p.sum(axis=1, keepdims=True)

    def probs(self, m, line):
        """Arrays (P(home covers), P(push)) for predicted home margins m against spread_line(s)."""
        m = np.atleast_1d(np.asarray(m, dtype=float))
        line = np.broadcast_to(np.atleast_1d(np.asarray(line, dtype=float)), m.shape)
        p = self.pmf(m)
        cover = (p * (K[None, :] > line[:, None])).sum(axis=1)
        push = (p * (K[None, :] == line[:, None])).sum(axis=1)
        return cover, push

    def describe(self):
        d = {"kind": self.kind, "n": self.n, "sd": round(self.sd, 2)}
        if hasattr(self, "key_ratio"):
            d["bandwidth"] = round(self.bandwidth, 2)
            d["key_number_ratio"] = {k: round(v, 2) for k, v in self.key_ratio.items()}
        return d


def no_push_prob(p_cover, p_push):
    """Chance the home side wins the bet given it isn't a push."""
    return p_cover / np.maximum(1.0 - p_push, 1e-9)
