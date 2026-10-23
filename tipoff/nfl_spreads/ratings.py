"""Point-in-time EPA power ratings: what each team's offence and defence looked like BEFORE a game.

For every team we keep an offensive rating (expected EPA/play gained) and a defensive rating
(expected EPA/play allowed). Within a season each rating is a recency-weighted average of the
team's per-game EPA/play, anchored by a preseason prior worth `prior_games` games:

    rating = (prior_games * prior + sum_i w_i x_i) / (prior_games + sum_i w_i),  w_i = 0.5 ** (games_ago / half_life)

The prior is last season's final rating pulled toward last season's league mean:
    prior = league_mean + carry * (final - league_mean)

No look-ahead: games are processed one date at a time. Every game on a date is rated from the
state before that date, and only then are that date's results folded in. Games without EPA
(not played yet) never update anything. The three parameters are chosen per test season by the
walk-forward harness using training seasons only.
"""
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RatingParams:
    prior_games: float = 6.0   # preseason prior's weight, in games
    carry: float = 0.6         # share of last season's (de-meaned) final rating carried over
    half_life: float = 8.0     # in-season recency half-life, in games (large = equal weights)

    def label(self):
        hl = "inf" if self.half_life >= 1000 else f"{self.half_life:g}"
        return f"k={self.prior_games:g} carry={self.carry:g} hl={hl}"


DEFAULT_GRID = tuple(RatingParams(k, c, h) for k in (4.0, 8.0, 12.0, 18.0) for c in (0.4, 0.6, 0.8)
                     for h in (5.0, 10.0, 1000.0))

RATING_COLS = ("home_off", "home_def", "away_off", "away_def", "home_n", "away_n")


class _Team:
    __slots__ = ("season", "s_off", "s_def", "s_w", "p_off", "p_def", "n")

    def __init__(self):
        self.season = None
        self.s_off = self.s_def = self.s_w = 0.0
        self.p_off = self.p_def = None
        self.n = 0


def pregame_ratings(games: pd.DataFrame, epa: pd.DataFrame, params: RatingParams = RatingParams()) -> pd.DataFrame:
    """One row per game (index game_id): each side's offensive/defensive rating before kickoff,
    plus how many of this season's games fed it. `games` needs game_id, season, gameday,
    home_team, away_team; `epa` needs game_id, team, off_epa, def_epa."""
    k, carry = params.prior_games, params.carry
    decay = 0.5 ** (1.0 / params.half_life)
    obs = {(r.game_id, r.team): (r.off_epa, r.def_epa) for r in epa.itertuples(index=False)
           if r.off_epa == r.off_epa and r.def_epa == r.def_epa}
    teams = defaultdict(_Team)
    season_sum = defaultdict(lambda: [0.0, 0])       # league mean off EPA/play per season (observed)
    out = {}

    def rating(t: _Team, season):
        if t.season != season:                       # first game of a new season: build the prior
            if t.season is None:
                prev_mean, f_off, f_def = 0.0, 0.0, 0.0
            else:
                ssum, sn = season_sum[t.season]
                prev_mean = ssum / sn if sn else 0.0
                f_off, f_def = _value(t, k)
            t.p_off = prev_mean + carry * (f_off - prev_mean)
            t.p_def = prev_mean + carry * (f_def - prev_mean)
            t.season, t.s_off, t.s_def, t.s_w, t.n = season, 0.0, 0.0, 0.0, 0
        return _value(t, k) + (t.n,)

    order = games.sort_values(["gameday", "game_id"])
    for _, day in order.groupby("gameday", sort=True):
        day_rows = list(day[["game_id", "season", "home_team", "away_team"]].itertuples(index=False))
        for g in day_rows:                           # rate everything on this date first ...
            h = rating(teams[g.home_team], g.season)
            a = rating(teams[g.away_team], g.season)
            out[g.game_id] = (h[0], h[1], a[0], a[1], h[2], a[2])
        for g in day_rows:                           # ... then fold in this date's results
            for tm in (g.home_team, g.away_team):
                x = obs.get((g.game_id, tm))
                if x is None:
                    continue
                t = teams[tm]
                t.s_off = t.s_off * decay + x[0]
                t.s_def = t.s_def * decay + x[1]
                t.s_w = t.s_w * decay + 1.0
                t.n += 1
                season_sum[g.season][0] += x[0]
                season_sum[g.season][1] += 1
    return pd.DataFrame.from_dict(out, orient="index", columns=list(RATING_COLS))


def _value(t: _Team, k):
    p_off = t.p_off or 0.0
    p_def = t.p_def or 0.0
    den = k + t.s_w
    if den <= 0:
        return p_off, p_def
    return (k * p_off + t.s_off) / den, (k * p_def + t.s_def) / den


def rating_diff(r: pd.DataFrame) -> pd.Series:
    """Home net rating minus away net rating (EPA/play): (off - def allowed) home - away."""
    return (r["home_off"] - r["home_def"]) - (r["away_off"] - r["away_def"])
