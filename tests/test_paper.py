"""Paper trading stays separate from the real card, and its journal speaks plainly.

    python -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tipoff import journal, paper
from tipoff.db import connect

DAY = "2026-10-22"
CFG = {"settings": {"bankroll": 2000, "model_weight": 0.0},
       "rules": [{"id": "min_edge", "kind": "gate", "status": "confirmed", "params": {"min": 0.02}}]}


def add_paper(con, strategy, result, price=100, stake=20, clv=0.03, status="graded"):
    con.execute("INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair, edge,"
                " stake, added_at, status, result, clv, paper, strategy) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (DAY, "ev1", "player_points", "kcp", "Kentavious Caldwell-Pope", "Over", 6.5, "hardrockbet", price,
                 0.52, 0.04, stake, "now", status, result, clv, strategy))
    con.commit()


def market(player="Kentavious Caldwell-Pope", edge=0.044, flags=()):
    return {"id": f"ev1|player_points|{player}|6.5|Over", "player": player, "side": "Over", "point": 6.5,
            "stat_label": "Points", "stake": 21.0, "price": 105, "fair_american": -104, "edge": edge,
            "flags": list(flags)}


class PaperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.tmp.name) / "t.db", check_same_thread=False)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_strategy_overrides(self):
        c = paper.strategy_cfg(CFG, {"id": "min3", "overrides": {"min_edge": 0.03}}, 1500)
        self.assertEqual(c["rules"][0]["params"]["min"], 0.03)
        self.assertEqual(c["settings"]["bankroll"], 1500)
        c = paper.strategy_cfg(CFG, {"id": "model15", "overrides": {"model_weight": 0.15}}, 2000)
        self.assertEqual(c["settings"]["model_weight"], 0.15)
        self.assertEqual(CFG["rules"][0]["params"]["min"], 0.02, "the real rules are never modified")

    def test_volume_strategy_overrides(self):
        cfg = {"settings": {"bankroll": 2000, "nightly_risk_cap": 0.08},
               "rules": [{"id": "min_edge", "kind": "gate", "status": "confirmed", "params": {"min": 0.02}},
                         {"id": "max_per_night", "kind": "gate", "status": "confirmed", "params": {"max": 12}}]}
        vol = next(st for st in paper.DEFAULT_STRATEGIES if st["id"] == "volume")
        c = paper.strategy_cfg(cfg, vol, 2000)
        self.assertEqual(c["rules"][0]["params"]["min"], 0.0)
        self.assertEqual(c["rules"][1]["params"]["max"], 100)
        self.assertEqual((c["settings"]["flat_stake"], c["settings"]["nightly_risk_cap"]), (10, 1.0))

    def test_bankroll_counts_only_that_strategy(self):
        add_paper(self.con, "current", "win", price=150, stake=20)   # +30
        add_paper(self.con, "current", "loss", stake=10)             # -10
        add_paper(self.con, "min3", "loss", stake=50)
        self.assertEqual(paper.bankroll(self.con, "current"), 2020.0)
        self.assertEqual(paper.bankroll(self.con, "min3"), 1950.0)

    def test_paper_bets_never_touch_the_real_card(self):
        add_paper(self.con, "current", None, status="locked")
        from fastapi.testclient import TestClient

        from tipoff import api
        with mock.patch.dict(api._state, {"con": self.con}), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TIPOFF_PASSWORD", None)
            c = TestClient(api.app, client=("127.0.0.1", 5000))
            self.assertEqual(c.get("/api/card", params={"date": DAY}).json()["legs"], [])
            c.post("/api/card/unlock", json={"date": DAY})
        self.assertEqual(self.con.execute("SELECT status FROM bets WHERE paper=1").fetchone()[0], "locked")

    def test_ledger_lists_bets_waiting_on_results(self):
        add_paper(self.con, "volume", None, status="locked")
        from fastapi.testclient import TestClient

        from tipoff import api
        with mock.patch.dict(api._state, {"con": self.con}), mock.patch("tipoff.api.grade"):
            os.environ.pop("TIPOFF_PASSWORD", None)
            c = TestClient(api.app, client=("127.0.0.1", 5000))
            r = c.get("/api/ledger", params={"source": "paper", "strategy": "volume"}).json()
            self.assertEqual([w["stake"] for w in r["waiting"]], [20])
            r = c.get("/api/ledger", params={"source": "paper", "strategy": "current"}).json()
            self.assertEqual(r["waiting"], [])

    def test_decision_entry_explains_and_passes(self):
        games = [{"away": "CLE", "home": "PHI"}]
        taken = market()
        passed = market("Joel Embiid", edge=0.011)
        journal.decision_entry(self.con, DAY, games, {"current": [taken], "min3": []}, [taken, passed],
                               {taken["id"]: {"verdict": "clear", "note": "no injury news."}}, 0.02)
        e = journal.entries(self.con)[0]
        self.assertIn("1 paper bet", e["title"])
        self.assertIn("about $4 profit per $100", e["body"])
        self.assertIn("Claude's news check: clear", e["body"])
        self.assertIn("Joel Embiid", e["body"])
        self.assertIn("short of the 2% bar", e["body"])

    def test_template_recap_uses_the_real_numbers(self):
        add_paper(self.con, "current", "win", price=150, stake=20, clv=0.05)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("tipoff.injuries.notify"):
            title, text = journal.recap(self.con, DAY)
        self.assertIn("+$30", title)
        self.assertIn("$2,030", title)
        self.assertIn("Too early", text)


if __name__ == "__main__":
    unittest.main()
