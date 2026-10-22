"""Point-in-time player features. Every number is built ONLY from games played before
the bet date, so the backtest never sees the future (no look-ahead bias).

League-aware: windows, the minimum history and the opponent-adjusted stats come from the
league's config (tipoff/leagues.py). NBA-only features (minutes trend, back-to-backs, season
points and rebounds) are None for leagues without them.
"""
import bisect
import math
from collections import defaultdict

from .leagues import NBA, get

# NBA names kept importable: the rest of the code (and older scripts) still use them.
MARKET_STAT = NBA.market_stat
OPP_STATS = NBA.opp_stats  # stats where we adjust for the opponent's defense


class FeatureStore:
    def __init__(self, con, league=None):
        self.league = lg = get(league)
        self.by_player = defaultdict(list)  # name_key -> rows sorted by date
        for r in con.execute("SELECT * FROM player_games ORDER BY game_date"):
            self.by_player[r["name_key"]].append(dict(r))
        self.player_dates = {k: [g["game_date"] for g in v] for k, v in self.by_player.items()}

        # What each defense allowed, game by game (rows of the teams that played against it).
        self.allowed = defaultdict(list)    # opp team -> [(date, {stat: value})]
        self.league_rows = []               # [(date, {stat: value})]
        cols = {r[1] for r in con.execute("PRAGMA table_info(team_games)")}
        opp_stats = [s for s in lg.opp_stats if s in cols]
        for r in con.execute("SELECT * FROM team_games ORDER BY game_date"):
            vals = {s: r[s] for s in opp_stats if r[s] is not None}
            self.allowed[r["opponent"]].append((r["game_date"], vals))
            self.league_rows.append((r["game_date"], vals))
        self.league_dates = [d for d, _ in self.league_rows]
        self.allowed_dates = {k: [d for d, _ in v] for k, v in self.allowed.items()}

    def game_row(self, key, date):
        """The player's actual box score on that date (for grading), or None if he didn't play."""
        dates = self.player_dates.get(key, [])
        i = bisect.bisect_left(dates, date)
        if i < len(dates) and dates[i] == date:
            return self.by_player[key][i]
        return None

    def _opp_factor(self, opp, stat, date):
        lg = self.league
        if stat not in lg.opp_stats or opp not in self.allowed:
            return 1.0
        i = bisect.bisect_left(self.allowed_dates[opp], date)
        recent = [v[stat] for _, v in self.allowed[opp][max(0, i - lg.opp_window):i] if stat in v]
        j = bisect.bisect_left(self.league_dates, date)
        lg_vals = [v[stat] for _, v in self.league_rows[max(0, j - lg.league_window):j] if stat in v]
        if len(recent) < lg.opp_min or not lg_vals or not sum(lg_vals):
            return 1.0
        raw = (sum(recent) / len(recent)) / (sum(lg_vals) / len(lg_vals))
        return 1 + 0.5 * (raw - 1)  # shrink halfway to average: a few weeks of games is a noisy sample

    def player(self, key, date, stat):
        """Features for one player on one date, or None if there's too little history."""
        lg = self.league
        dates = self.player_dates.get(key)
        if not dates:
            return None
        i = bisect.bisect_left(dates, date)
        hist = self.by_player[key][:i]
        today = self.game_row(key, date)
        season = today["season"] if today else (hist[-1]["season"] if hist else None)
        this_season = [g for g in hist if g["season"] == season]
        if len(hist) < lg.min_games:
            return None
        vals = [g[stat] for g in hist if g[stat] is not None]
        if not vals:
            return None
        recent = vals[-lg.recent_games:]
        mean10 = sum(recent) / len(recent)
        sd10 = math.sqrt(sum((v - mean10) ** 2 for v in recent) / max(1, len(recent) - 1))
        season_vals = [g[stat] for g in this_season if g[stat] is not None]
        season_mean = sum(season_vals) / len(season_vals) if season_vals else mean10
        last = hist[-1]["game_date"]
        rest_days = (_d(date) - _d(last)).days - 1
        team = today["team"] if today else hist[-1]["team"]
        opp = today["opponent"] if today else None
        home = today["home"] if today else None
        opp_f = self._opp_factor(opp, stat, date) if opp else 1.0

        # Projection: recent form blended with the season, scaled by the matchup.
        w = min(len(season_vals), lg.season_full) / lg.season_full
        base = 0.55 * mean10 + 0.45 * (w * season_mean + (1 - w) * mean10)
        if lg.has_minutes:
            mins = [g["minutes"] for g in hist[-5:] if g["minutes"] is not None]
            mins_season = [g["minutes"] for g in this_season if g["minutes"] is not None]
            min_trend = (sum(mins) / len(mins)) / (sum(mins_season) / len(mins_season)) if mins and mins_season else 1.0
            min_trend = 1 + 0.5 * (max(0.6, min(1.4, min_trend)) - 1)
            extra = {"season_pts": _avg(this_season, "pts"), "season_reb": _avg(this_season, "reb"),
                     "b2b": rest_days == 0, "min_last5": sum(mins) / len(mins) if mins else None,
                     "min_trend": min_trend}
        else:  # no minutes in this league's box scores, and no back-to-backs worth the name
            min_trend = 1.0
            extra = {"season_pts": None, "season_reb": None, "b2b": None, "min_last5": None, "min_trend": None}
        return {
            "proj": base * opp_f * min_trend, "sd": sd10, "mean10": mean10, "season_mean": season_mean,
            "games_played": len(this_season), "rest_days": rest_days,
            "home": home, "team": team, "opponent": opp, "opp_factor": opp_f, **extra,
        }


def _avg(rows, stat):
    v = [g[stat] for g in rows if g[stat] is not None]
    return sum(v) / len(v) if v else 0.0


def _d(s):
    from datetime import date
    return date.fromisoformat(s)
