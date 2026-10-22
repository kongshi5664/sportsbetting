"""The weekly review proposes changes only on clear evidence, and only a person applies them.

    python -m unittest discover tests
"""
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tipoff import review
from tipoff.db import connect

RULES = [
    {"id": "min_edge", "name": "Minimum value", "status": "confirmed", "kind": "gate", "params": {"min": 0.02}},
    {"id": "role_player_props", "name": "Prefer role players", "status": "testing", "kind": "prefer",
     "params": {"max_season_pts": 15}},
    {"id": "skip_early_season", "name": "Skip early season", "status": "testing", "kind": "avoid",
     "params": {"min_games": 8}},
]
CFG = {"settings": {"sharp_weight": 0.5}, "rules": RULES}


def ctx(pts=10.0, games=20, sharp=True):
    return {"f": {"games_played": games, "b2b": False, "season_pts": pts, "season_reb": 4.0, "min_trend": 1.0,
                  "opp_factor": 1.0, "home": 1, "rest_days": 1},
            "stat": "pts", "side": "Over", "p_model": 0.55, "p_market": 0.52, "sharp": sharp, "testing": []}


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Shared across threads like the server's own connection (the API test runs requests in a worker).
        self.con = connect(Path(self.tmp.name) / "t.db", check_same_thread=False)
        self.rng = random.Random(7)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def add(self, n, clv, context, edge=0.05):
        for _ in range(n):
            self.con.execute(
                "INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair, edge,"
                " stake, added_at, status, clv, result, context) VALUES ('2026-11-01','e','player_points','k','P',"
                "'Over',10.5,'hardrockbet',-110,0.55,?,20,'now','graded',?,'win',?)",
                (edge, clv + self.rng.gauss(0, 0.02), json.dumps(context)))
        self.con.commit()

    def finding(self, rep, fid):
        return next(f for f in rep["findings"] if f["id"] == fid)

    def test_thin_data_proposes_nothing(self):
        self.add(10, 0.08, ctx(pts=10))
        self.add(10, 0.0, ctx(pts=25))
        rep = review.run(self.con, CFG)
        self.assertTrue(all(f["proposal"] is None for f in rep["findings"]))
        self.assertIn("Too few", self.finding(rep, "rule:role_player_props")["verdict"])

    def test_clear_win_proposes_promotion(self):
        self.add(40, 0.06, ctx(pts=10))   # role players: beat the close by more
        self.add(40, 0.00, ctx(pts=25))
        f = self.finding(review.run(self.con, CFG), "rule:role_player_props")
        self.assertEqual(f["proposal"], {"type": "rule_status", "rule": "role_player_props", "value": "confirmed"})

    def test_avoid_rule_that_helps_gets_retired(self):
        self.add(40, 0.06, ctx(games=3))  # the "avoid" group actually does better
        self.add(40, 0.00, ctx(games=30))
        f = self.finding(review.run(self.con, CFG), "rule:skip_early_season")
        self.assertEqual(f["proposal"]["value"], "retired")

    def test_low_value_bets_losing_raise_the_minimum(self):
        self.add(40, -0.03, ctx(), edge=0.025)
        self.add(40, 0.03, ctx(), edge=0.05)
        f = self.finding(review.run(self.con, CFG), "setting:min_edge")
        self.assertEqual(f["proposal"], {"type": "setting", "rule": "min_edge", "key": "min", "value": 0.03})

    def test_applying_writes_rules_and_logs(self):
        self.add(40, 0.06, ctx(pts=10))
        self.add(40, 0.00, ctx(pts=25))
        rules_path = Path(self.tmp.name) / "rules.json"
        rules_path.write_text(json.dumps(CFG), encoding="utf-8")
        from fastapi.testclient import TestClient

        from tipoff import api
        with mock.patch.object(api, "RULES_PATH", rules_path), mock.patch.dict(api._state, {"con": self.con}), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TIPOFF_PASSWORD", None)
            c = TestClient(api.app, client=("127.0.0.1", 5000))
            r = c.post("/api/review/apply", json={"id": "rule:role_player_props"})
            self.assertEqual(r.status_code, 200, r.text)
        saved = json.loads(rules_path.read_text(encoding="utf-8"))
        self.assertEqual(next(x for x in saved["rules"] if x["id"] == "role_player_props")["status"], "confirmed")
        self.assertEqual(self.con.execute("SELECT decision FROM review_log").fetchone()[0], "applied")


if __name__ == "__main__":
    unittest.main()
