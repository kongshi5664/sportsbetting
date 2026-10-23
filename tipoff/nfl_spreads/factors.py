"""Factor registry: each factor is a small function that turns one game into pre-game features.

A factor gets two things and nothing else:
  game  the game's PRE-GAME fields only (teams, date, week, rest, site, weather, starting QBs).
        Scores, results and market lines are stripped out, so a factor cannot read the outcome
        or lean on the closing line it is meant to be judged against.
  past  a view of completed games strictly BEFORE the game's date (`past.team_games(team)`,
        `past.last_game(team)`), which hands out full rows (scores, QBs) of earlier games only.

It returns {feature_name: float}, oriented home minus away (positive = favours the home team).
Each feature gets one coefficient, fitted by the margin model on training seasons only.

Add a factor:

    @register("my_factor", "one line on what it measures")
    def my_factor(game, past):
        return {"my_factor_diff": ...}

then add a no-look-ahead test (tests/test_nfl_spreads.py) and run
`python -m tipoff.nfl_spreads.experiment my_factor`.

Starting QBs: for completed games nflverse lists who actually started. That is known at kickoff
(inactives are out ~90 minutes before), but a bet placed days earlier may not know it.
"""
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

import pandas as pd

PREGAME_FIELDS = ("game_id", "season", "game_type", "week", "gameday", "gametime", "home_team", "away_team",
                  "location", "home_rest", "away_rest", "div_game", "roof", "surface", "temp", "wind",
                  "home_qb_id", "away_qb_id", "home_qb_name", "away_qb_name")


@dataclass(frozen=True)
class Factor:
    name: str
    description: str
    fn: Callable


REGISTRY: dict = {}


def register(name, description):
    def deco(fn):
        REGISTRY[name] = Factor(name, description, fn)
        return fn
    return deco


def get(names):
    missing = [n for n in names if n not in REGISTRY]
    if missing:
        raise SystemExit(f"Unknown factor(s): {', '.join(missing)}. Known: {', '.join(sorted(REGISTRY))}")
    return [REGISTRY[n] for n in names]


class History:
    """All completed games, indexed per team by date. Factors only ever see `before(date)` views."""

    def __init__(self, games: pd.DataFrame):
        done = games[games["result"].notna()].sort_values(["gameday", "game_id"])
        self._by_team = defaultdict(list)
        for g in done.to_dict("records"):
            for tm in (g["home_team"], g["away_team"]):
                self._by_team[tm].append(g)
        self._dates = {tm: [g["gameday"] for g in lst] for tm, lst in self._by_team.items()}

    def before(self, cutoff):
        return PastView(self, cutoff)


class PastView:
    """Completed games strictly before `cutoff` (a YYYY-MM-DD date)."""

    def __init__(self, history: History, cutoff):
        self._h, self.cutoff = history, cutoff

    def team_games(self, team):
        i = bisect_left(self._h._dates.get(team, []), self.cutoff)
        return self._h._by_team.get(team, [])[:i]

    def last_game(self, team):
        i = bisect_left(self._h._dates.get(team, []), self.cutoff)
        return self._h._by_team[team][i - 1] if i else None


def pregame(game: dict) -> dict:
    return {k: game.get(k) for k in PREGAME_FIELDS}


def compute(games: pd.DataFrame, factors) -> pd.DataFrame:
    """Every factor's features for every game in `games` (index game_id)."""
    hist = History(games)
    rows = {}
    for g in games.to_dict("records"):
        pg, past = pregame(g), hist.before(g["gameday"])
        feats = {}
        for f in factors:
            feats.update(f.fn(pg, past))
        rows[g["game_id"]] = feats
    return pd.DataFrame.from_dict(rows, orient="index").fillna(0.0)


# ---------------------------------------------------------------- example factors

def days_rest(game, past, side):
    """Days since this team's previous game; 7 for a season opener (nflverse's convention)."""
    team = game[f"{side}_team"]
    last = past.last_game(team)
    if last is None or last["season"] != game["season"]:
        return 7
    return (pd.Timestamp(game["gameday"]) - pd.Timestamp(last["gameday"])).days


@register("rest", "rest days (capped 6-14: byes and mini-byes) and short weeks (<=5 days), home minus away")
def rest(game, past):
    h, a = days_rest(game, past, "home"), days_rest(game, past, "away")
    cap = lambda d: min(max(d, 6), 14)  # noqa: E731
    return {"rest_diff": float(cap(h) - cap(a)), "short_week_diff": float((h <= 5) - (a <= 5))}


def last_starter(team, past):
    last = past.last_game(team)
    if last is None:
        return None
    return last["home_qb_id"] if last["home_team"] == team else last["away_qb_id"]


def qb_changed(game, past, side):
    now = game.get(f"{side}_qb_id")
    before = last_starter(game[f"{side}_team"], past)
    if not now or not before or now != now or before != before:  # unknown (or NaN): no signal
        return 0
    return int(now != before)


@register("qb_change", "starting QB differs from the team's previous game's starter, home minus away")
def qb_change(game, past):
    return {"qb_change_diff": float(qb_changed(game, past, "home") - qb_changed(game, past, "away"))}
