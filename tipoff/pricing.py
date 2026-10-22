"""Odds math. Everything works in decimal odds and win probabilities internally."""
import math
from statistics import median


def to_decimal(american: int) -> float:
    return 1 + american / 100 if american > 0 else 1 + 100 / -american


def to_american(p: float) -> int:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -round(100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def devig_pair(over_price: int, under_price: int):
    """Remove the book's margin proportionally. Returns (p_over, p_under)."""
    a, b = 1 / to_decimal(over_price), 1 / to_decimal(under_price)
    return a / (a + b), b / (a + b)


def consensus(prices_by_book: dict, exclude=(), sharp=(), sharp_weight=0.0):
    """prices_by_book: {book: {"Over": price, "Under": price}} at ONE line.
    Median of each book's de-vigged Over probability. When sharp books (e.g. Pinnacle) price the
    line, their average counts for `sharp_weight` and the median of the rest for the remainder:
    sharp books move first and are wrong less often. None if no book has both sides."""
    p = {b: devig_pair(s["Over"], s["Under"])[0]
         for b, s in prices_by_book.items() if b not in exclude and "Over" in s and "Under" in s}
    if not p:
        return None
    sharp_ps = [v for b, v in p.items() if b in sharp]
    rest = [v for b, v in p.items() if b not in sharp]
    if not sharp_ps or sharp_weight <= 0:
        return median(p.values())
    s_avg = sum(sharp_ps) / len(sharp_ps)
    return s_avg if not rest else sharp_weight * s_avg + (1 - sharp_weight) * median(rest)


def ev(p_win: float, american: int) -> float:
    return p_win * to_decimal(american) - 1


def kelly_stake(p_win: float, american: int, bankroll: float, fraction=0.25, cap_units=2.0):
    d = to_decimal(american)
    f = max(0.0, (p_win * d - 1) / (d - 1)) * fraction
    return min(f * bankroll, cap_units * bankroll / 100)


# ---- distributions for turning a projection into P(over) ----

def _poisson_cdf(k: int, mu: float) -> float:
    term = math.exp(-mu)
    total = term
    for i in range(1, k + 1):
        term *= mu / i
        total += term
    return min(total, 1.0)


def _negbin_cdf(k: int, mu: float, var: float) -> float:
    # Over-dispersed counts (rebounds, assists) fit a negative binomial better than Poisson.
    if var <= mu * 1.02:
        return _poisson_cdf(k, mu)
    p = mu / var
    r = mu * p / (1 - p)
    total, term = 0.0, p ** r
    for i in range(0, k + 1):
        if i > 0:
            term *= (i - 1 + r) / i * (1 - p)
        total += term
    return min(total, 1.0)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def prob_over(line: float, mu: float, sd: float, stat: str):
    """Returns (p_over, p_push). Points use a normal; counting stats use negative binomial."""
    if mu <= 0:
        return 0.0, 0.0
    is_int = float(line).is_integer()
    if stat == "pts":
        sd = max(sd, 0.35 * mu, 2.0)
        if is_int:
            p_push = _normal_cdf((line + 0.5 - mu) / sd) - _normal_cdf((line - 0.5 - mu) / sd)
            return 1 - _normal_cdf((line + 0.5 - mu) / sd), p_push
        return 1 - _normal_cdf((line - mu) / sd), 0.0
    var = max(sd * sd, mu)
    k = int(math.floor(line))
    if is_int:
        below = _negbin_cdf(k - 1, mu, var)
        at = _negbin_cdf(k, mu, var) - below
        return 1 - below - at, at
    return 1 - _negbin_cdf(k, mu, var), 0.0
