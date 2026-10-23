"""NFL spread model: sign convention, pbp aggregation, no look-ahead in ratings and factors,
cover/push probabilities at key numbers, walk-forward fitting only on past seasons, and the
factor registry/experiment. No network: tiny synthetic leagues and fixtures only.

    python -m unittest tests.test_nfl_spreads
"""
import contextlib
import csv
import io
import gzip
import random
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from tipoff.nfl_spreads import experiment, factors, harness, load
from tipoff.nfl_spreads.cover import CoverModel
from tipoff.nfl_spreads.data import GAME_COLS, aggregate_pbp, connect_nfl, game_rows, load_games
from tipoff.nfl_spreads.model import fit
from tipoff.nfl_spreads.ratings import RatingParams, pregame_ratings

TEAMS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
SMALL_GRID = (RatingParams(4, 0.6, 1000.0), RatingParams(8, 0.6, 5.0))


def synthetic(seasons=range(2006, 2011), weeks=12, seed=7):
    """A little league: 8 teams, round-robin-ish weekly games (one Thursday game per week), true
    strengths that drift between seasons, EPA that tracks strength, closing lines near the truth,
    and occasional QB changes."""
    rng = random.Random(seed)
    strength = {t: rng.gauss(0, 0.1) for t in TEAMS}
    games, epa = [], []
    qb = {t: f"{t}-QB1" for t in TEAMS}
    for s in seasons:
        strength = {t: 0.6 * v + rng.gauss(0, 0.07) for t, v in strength.items()}
        start = date(s, 9, 10)
        for w in range(1, weeks + 1):
            order = TEAMS[:]
            rng.shuffle(order)
            for i in range(0, len(order), 2):
                h, a = order[i], order[i + 1]
                for t in (h, a):
                    if rng.random() < 0.05:
                        qb[t] = f"{t}-QB{rng.randint(1, 3)}"
                day = start + timedelta(days=7 * (w - 1) + (-3 if i == 0 else 0))
                true = 2.0 + 60 * (strength[h] - strength[a])
                res = round(true + rng.gauss(0, 13))
                gid = f"{s}_{w:02d}_{a}_{h}"
                games.append({"game_id": gid, "season": s, "game_type": "REG", "week": w,
                              "gameday": day.isoformat(), "gametime": "13:00", "home_team": h, "away_team": a,
                              "location": "Home", "result": float(res), "spread_line": round(true * 2) / 2,
                              "home_qb_id": qb[h], "away_qb_id": qb[a], "home_qb_name": qb[h], "away_qb_name": qb[a],
                              "home_rest": 7, "away_rest": 7, "div_game": 0, "roof": "outdoors", "surface": "grass",
                              "temp": 60.0, "wind": 5.0})
                for t, o, sign in ((h, a, 1), (a, h, -1)):
                    epa.append({"game_id": gid, "team": t, "season": s, "week": w, "opponent": o,
                                "off_epa": strength[t] + sign * res / 600 + rng.gauss(0, 0.05),
                                "def_epa": strength[o] - sign * res / 600 + rng.gauss(0, 0.05)})
    return pd.DataFrame(games), pd.DataFrame(epa)


def cut_and_alter(games, epa, cutoff):
    """Same league, but every game on/after `cutoff` has a different result and EPA, a new QB,
    and an extra game is added later on: anything dated before `cutoff` must not notice."""
    g, e = games.copy(), (epa.copy() if epa is not None else None)
    late = g["gameday"] >= cutoff
    g.loc[late, "result"] = -g.loc[late, "result"] + 21
    g.loc[late, "home_qb_id"] = "SOMEONE-NEW"
    late_ids = set(g.loc[late, "game_id"])
    if e is not None:
        e.loc[e["game_id"].isin(late_ids), "off_epa"] += 0.9
    extra = g.iloc[[-1]].copy()
    extra["game_id"], extra["gameday"] = "extra", "2030-01-01"
    return pd.concat([g, extra], ignore_index=True), e


class SignConventionTest(unittest.TestCase):
    ROW = {"game_id": "2025_01_DAL_PHI", "season": "2025", "game_type": "REG", "week": "1", "gameday": "2025-09-04",
           "gametime": "20:20", "away_team": "DAL", "away_score": "20", "home_team": "PHI", "home_score": "24",
           "location": "Home", "result": "4", "spread_line": "8.5", "home_moneyline": "-425", "away_moneyline": "330",
           "home_rest": "7", "away_rest": "7", "div_game": "1", "home_qb_id": "00-1", "away_qb_id": "00-2"}

    def test_spread_line_is_the_home_margin_and_home_favourite_is_positive(self):
        (row,) = game_rows([self.ROW])
        g = dict(zip(GAME_COLS, row))
        self.assertEqual(g["spread_line"], 8.5)          # PHI -8.5 at home, the moneyline favourite
        self.assertLess(g["home_moneyline"], 0)
        self.assertEqual(g["result"], 4.0)               # home score - away score
        # PHI won by 4 but was laid 8.5: the away side covered
        df = pd.DataFrame([{"result": 4.0, "spread_line": 8.5}])
        self.assertEqual(harness.ats(df, np.array([1]))["l"], 1)
        self.assertEqual(harness.ats(df, np.array([-1]))["w"], 1)
        push = pd.DataFrame([{"result": 3.0, "spread_line": 3.0}])
        self.assertEqual(harness.ats(push, np.array([1]))["p"], 1)

    def test_moved_franchises_get_one_code(self):
        rows = game_rows([{**self.ROW, "home_team": "STL", "away_team": "SD"},
                          {**self.ROW, "game_id": "x", "home_team": "OAK"}])
        self.assertEqual((rows[0][6], rows[0][7], rows[1][6]), ("LA", "LAC", "LV"))


class PbpAggregationTest(unittest.TestCase):
    def test_team_game_offence_and_defence(self):
        pbp = pd.DataFrame([
            {"game_id": "g", "season": 2010, "week": 1, "posteam": "STL", "defteam": "SF", "play_type": "pass", "epa": 1.0, "success": 1, "pass": 1},
            {"game_id": "g", "season": 2010, "week": 1, "posteam": "STL", "defteam": "SF", "play_type": "run", "epa": -0.5, "success": 0, "pass": 0},
            {"game_id": "g", "season": 2010, "week": 1, "posteam": "STL", "defteam": "SF", "play_type": "punt", "epa": 3.0, "success": 1, "pass": 0},
            {"game_id": "g", "season": 2010, "week": 1, "posteam": "SF", "defteam": "STL", "play_type": "run", "epa": 0.2, "success": 1, "pass": 0},
            {"game_id": "g", "season": 2010, "week": 1, "posteam": "SF", "defteam": "STL", "play_type": "no_play", "epa": 5.0, "success": 1, "pass": 1},
        ])
        a = aggregate_pbp(pbp).set_index("team")
        self.assertEqual(set(a.index), {"LA", "SF"})
        self.assertEqual(a.loc["LA", "off_plays"], 2)
        self.assertAlmostEqual(a.loc["LA", "off_epa"], 0.25)
        self.assertAlmostEqual(a.loc["LA", "off_pass_epa"], 1.0)
        self.assertAlmostEqual(a.loc["LA", "off_rush_epa"], -0.5)
        self.assertAlmostEqual(a.loc["LA", "def_epa"], 0.2)      # what SF's offence did against LA
        self.assertAlmostEqual(a.loc["SF", "def_epa"], 0.25)
        self.assertEqual(a.loc["LA", "opponent"], "SF")


class LoaderTest(unittest.TestCase):
    def test_load_is_idempotent_and_needs_no_network(self):
        games, _ = synthetic(seasons=[2010], weeks=2)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            cache = Path(d) / "cache"
            (cache / "pbp").mkdir(parents=True)
            with open(cache / "games.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(games.columns))
                w.writeheader()
                w.writerows(games.to_dict("records"))
            plays = [{"game_id": g.game_id, "season": 2010, "week": g.week, "posteam": t, "defteam": o,
                      "play_type": "pass", "epa": 0.1, "success": 1, "pass": 1}
                     for g in games.itertuples() for t, o in ((g.home_team, g.away_team), (g.away_team, g.home_team))]
            with gzip.open(cache / "pbp" / "play_by_play_2010.csv.gz", "wt", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(plays[0]))
                w.writeheader()
                w.writerows(plays)
            db = Path(d) / "nfl.db"
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()):
                    load.load([2010], db, cache=cache, offline=True)
            con = connect_nfl(db)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM nfl_games").fetchone()[0], len(games))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM nfl_team_game_epa").fetchone()[0], 2 * len(games))
            self.assertEqual(len(load_games(con)), len(games))
            con.close()

    def test_season_ranges(self):
        self.assertEqual(load.parse_seasons(["2006-2008", "2010"]), [2006, 2007, 2008, 2010])


class RatingsNoLookAheadTest(unittest.TestCase):
    def test_ratings_ignore_the_game_itself_and_everything_after(self):
        games, epa = synthetic()
        cutoff = "2009-10-01"
        full = pregame_ratings(games, epa, RatingParams(6, 0.6, 8))
        g2, e2 = cut_and_alter(games, epa, cutoff)
        alt = pregame_ratings(g2, e2, RatingParams(6, 0.6, 8))
        upto = games.loc[games["gameday"] <= cutoff, "game_id"]   # includes games ON the cutoff date
        pd.testing.assert_frame_equal(full.loc[upto], alt.loc[upto])
        later = games.loc[games["gameday"] > "2009-10-08", "game_id"]
        self.assertFalse(full.loc[later].equals(alt.loc[later]))  # the alteration did matter later

    def test_first_game_of_a_season_uses_the_regressed_prior(self):
        games, epa = synthetic()
        r = pregame_ratings(games, epa, RatingParams(6, 0.0, 8))   # carry 0: prior is the league mean
        s08 = games[games["season"] == 2008].sort_values("gameday")
        vals = set()
        for t in TEAMS:                                           # each team's 2008 opener
            g = s08[(s08["home_team"] == t) | (s08["away_team"] == t)].iloc[0]
            vals.add(round(r.loc[g["game_id"], "home_off" if g["home_team"] == t else "away_off"], 9))
        self.assertEqual(len(vals), 1)


class FactorTest(unittest.TestCase):
    def test_factors_never_see_the_future_or_the_result(self):
        games, _ = synthetic()
        facs = factors.get(["rest", "qb_change"])
        full = factors.compute(games, facs)
        g2, _ = cut_and_alter(games, None, "2009-10-01")
        # the games ON the cutoff keep their own QB, so only later inputs differ
        on = games["gameday"] == "2009-10-01"
        g2.loc[g2["game_id"].isin(games.loc[on, "game_id"]), "home_qb_id"] = games.loc[on, "home_qb_id"].to_numpy()
        alt = factors.compute(g2, facs)
        upto = games.loc[games["gameday"] <= "2009-10-01", "game_id"]
        pd.testing.assert_frame_equal(full.loc[upto], alt.loc[upto])

    def test_pregame_view_strips_results_and_lines(self):
        seen = {}

        @factors.register("_spy", "test only")
        def spy(game, past):
            seen.update(game)
            for g in past.team_games(game["home_team"]):
                self.assertLess(g["gameday"], game["gameday"])
            return {"spy": 0.0}
        try:
            games, _ = synthetic(seasons=[2010], weeks=3)
            factors.compute(games, factors.get(["_spy"]))
        finally:
            factors.REGISTRY.pop("_spy")
        for k in ("result", "spread_line", "home_score", "away_score", "home_moneyline"):
            self.assertNotIn(k, seen)

    def test_rest_counts_byes_and_short_weeks(self):
        g = pd.DataFrame([
            {"game_id": "a", "season": 2010, "gameday": "2010-09-12", "home_team": "X", "away_team": "Y", "result": 3.0},
            {"game_id": "b", "season": 2010, "gameday": "2010-09-16", "home_team": "X", "away_team": "Z", "result": 3.0},
            {"game_id": "c", "season": 2010, "gameday": "2010-09-26", "home_team": "Y", "away_team": "X", "result": 3.0},
        ])
        past = factors.History(g)
        row = lambda gid: factors.pregame(g.set_index("game_id").loc[gid].to_dict() | {"game_id": gid})  # noqa: E731
        b = factors.REGISTRY["rest"].fn(row("b"), past.before("2010-09-16"))
        self.assertEqual(b["short_week_diff"], 1.0)              # X on 4 days, Z opening its season (7)
        c = factors.REGISTRY["rest"].fn(row("c"), past.before("2010-09-26"))
        self.assertEqual(c["rest_diff"], 14 - 10)                 # Y off a bye (14) vs X (10 days)

    def test_qb_change_compares_with_the_previous_starter(self):
        g = pd.DataFrame([
            {"game_id": "a", "season": 2010, "gameday": "2010-09-12", "home_team": "X", "away_team": "Y",
             "home_qb_id": "x1", "away_qb_id": "y1", "result": 3.0},
            {"game_id": "b", "season": 2010, "gameday": "2010-09-19", "home_team": "Y", "away_team": "X",
             "home_qb_id": "y1", "away_qb_id": "x2", "result": 3.0},
        ])
        f = factors.REGISTRY["qb_change"].fn(factors.pregame(g.iloc[1].to_dict()), factors.History(g).before("2010-09-19"))
        self.assertEqual(f["qb_change_diff"], -1.0)               # away team X switched QBs

    def test_unknown_factor_is_an_error(self):
        with self.assertRaises(SystemExit):
            factors.get(["nope"])


class CoverModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Training margins that bunch on 3 and 7 the way NFL games do.
        rng = np.random.default_rng(1)
        preds = rng.normal(2, 5, 4000)
        margins = np.rint(preds + rng.normal(0, 13, 4000))
        swap = rng.random(4000) < 0.25
        margins[swap] = rng.choice([3, -3, 7, -7], swap.sum())
        margins[margins == 0] = 1
        cls.cm = CoverModel(margins - preds, margins, preds)

    def test_probabilities_add_up_and_pushes_only_on_whole_numbers(self):
        c, p = self.cm.probs([2.5, 2.5], [3.0, 3.5])
        self.assertGreater(p[0], 0.0)
        self.assertEqual(p[1], 0.0)
        self.assertAlmostEqual(self.cm.pmf([2.5]).sum(), 1.0)
        self.assertTrue(0 < c[0] < 1 and 0 < c[1] < 1)

    def test_key_numbers_push_more_often(self):
        m = np.array([3.0, 3.0, 7.0, 7.0])
        _, push = self.cm.probs(m, [3.0, 2.0, 7.0, 8.0])
        self.assertGreater(push[0], 1.5 * push[1])
        self.assertGreater(push[2], 1.5 * push[3])
        _, p0 = self.cm.probs([0.0], [0.0])
        self.assertLess(p0[0], 0.02)                              # ties almost never happen

    def test_a_bigger_predicted_margin_covers_more(self):
        c, _ = self.cm.probs([0.0, 3.0, 6.0, 9.0], [3.5] * 4)
        self.assertTrue(np.all(np.diff(c) > 0))

    def test_normal_fallback_with_few_residuals(self):
        cm = CoverModel(np.zeros(10))
        self.assertIn("fallback", cm.kind)
        c, p = cm.probs([3.5], [3.5])
        self.assertAlmostEqual(c[0] + p[0], 0.5, places=2)


class WalkForwardTest(unittest.TestCase):
    CFG = harness.Config(first_test=2008, report_from=2009, train_start=2007, grid=SMALL_GRID, min_blend_rows=50)

    def test_never_fits_on_the_test_season(self):
        games, epa = synthetic()
        run = harness.walk_forward(games, epa, (), self.CFG)
        self.assertTrue(run.fits)
        for f in run.fits:
            self.assertLess(f["train_seasons"][1], f["season"])
        # Rewrite every result of 2010: 2010's fit and predictions must not move.
        g2 = games.copy()
        g2.loc[g2["season"] == 2010, "result"] = 40.0
        run2 = harness.walk_forward(g2, epa, (), self.CFG)
        f1 = next(f for f in run.fits if f["season"] == 2010)
        f2 = next(f for f in run2.fits if f["season"] == 2010)
        self.assertEqual(f1, f2)
        p1 = run.preds[run.preds["season"] == 2010]["pred"].to_numpy()
        p2 = run2.preds[run2.preds["season"] == 2010]["pred"].to_numpy()
        np.testing.assert_allclose(p1, p2)

    def test_predictions_only_use_earlier_games(self):
        games, epa = synthetic()
        cutoff = "2010-10-15"
        run = harness.walk_forward(games, epa, ("rest", "qb_change"), self.CFG)
        g2, e2 = cut_and_alter(games, epa, cutoff)
        g2 = g2[g2["game_id"] != "extra"]
        run2 = harness.walk_forward(g2, e2, ("rest", "qb_change"), self.CFG)
        a = run.preds.set_index("game_id")
        b = run2.preds.set_index("game_id")
        before = games.loc[(games["gameday"] < cutoff) & (games["season"] >= 2008), "game_id"]
        np.testing.assert_allclose(a.loc[before, "pred"], b.loc[before, "pred"])

    def test_model_fit_recovers_hfa_and_scale(self):
        rng = np.random.default_rng(3)
        n = 2000
        df = pd.DataFrame({"season": np.repeat([2010, 2011], n // 2), "location": "Home",
                           "diff": rng.normal(0, 0.1, n)})
        df["result"] = np.where(df["season"] == 2010, 3.0, 1.0) + 60 * df["diff"] + rng.normal(0, 1, n)
        m = fit(df, (), hfa_seasons=1)
        self.assertAlmostEqual(m.scale, 60, delta=1.5)
        self.assertAlmostEqual(m.hfa, 1, delta=0.2)                # the latest season's HFA
        self.assertAlmostEqual(m.season_hfa[2010], 3, delta=0.2)

    def test_evaluate_and_report_render(self):
        games, epa = synthetic()
        run = harness.walk_forward(games, epa, (), self.CFG)
        rep = harness.evaluate(run, self.CFG)
        self.assertEqual(set(rep["overall"]["edge_tiers"]), {lab for _, _, lab in harness.EDGE_TIERS})
        self.assertIn("# NFL spreads", harness.markdown(rep, harness.upcoming(run)))


class ExperimentTest(unittest.TestCase):
    def test_baseline_vs_factors_side_by_side(self):
        games, epa = synthetic()
        reps = experiment.compare(games, epa, ["rest", "qb_change"], WalkForwardTest.CFG)
        self.assertEqual([r["name"] for r in reps], ["baseline", "+rest", "+qb_change", "+rest+qb_change"])
        hdr, rows = experiment.table(reps)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0][3], "+0.000")
        self.assertIn("qb_change_diff", rows[2][-1])
        self.assertIn("| variant |", experiment.markdown(reps, WalkForwardTest.CFG))


if __name__ == "__main__":
    unittest.main()
