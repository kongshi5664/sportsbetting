"""The injury watcher only speaks up when something changes for tonight's players.

    python -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tipoff import injuries
from tipoff.db import connect

DAY = "2026-10-22"


def entry(name, status, updated, team="CLE", detail="note"):
    return {"name_key": name.lower().replace(" ", ""), "player": name, "team": team, "status": status,
            "detail": detail, "updated": updated}


class InjuryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_only_changes_are_news(self):
        old = entry("Long Term", "Out", "2026-09-21T19:50Z")
        today = entry("Jarrett Allen", "Questionable", "2026-10-22T17:00Z")
        first = injuries.changes(self.con, [old, today], DAY)
        self.assertEqual([i["player"] for i in first], ["Jarrett Allen"], "an injury from September is not news today")
        self.assertEqual(injuries.changes(self.con, [old, today], DAY), [], "same statuses again: quiet")
        ruled_out = entry("Jarrett Allen", "Out", "2026-10-22T22:30Z")
        news = injuries.changes(self.con, [old, ruled_out], DAY)
        self.assertEqual((news[0]["status"], news[0]["was"]), ("Out", "Questionable"))

    def test_dropping_off_the_report_reads_as_cleared(self):
        injuries.changes(self.con, [entry("Jarrett Allen", "Questionable", "2026-10-22T17:00Z")], DAY)
        news = injuries.changes(self.con, [], DAY)
        self.assertEqual((news[0]["status"], news[0]["was"]), ("Active", "Questionable"))

    def test_alert_names_a_card_bet_that_would_void(self):
        self.con.execute("INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price,"
                         " fair, edge, stake, added_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (DAY, "ev1", "player_rebounds", "jarrettallen", "Jarrett Allen", "Over", 9.5, "hardrockbet",
                          -110, 0.55, 0.05, 20, "now"))
        i = entry("Jarrett Allen", "Out", "2026-10-22T22:30Z") | {"was": "Questionable"}
        lines = injuries.message(self.con, i, ("Jarrett Allen", "ev1", "CLE @ PHI", "2026-10-22T23:10:00Z"), DAY)
        self.assertIn("Out (was Questionable)", lines[0])
        self.assertTrue(any("On your card" in l for l in lines))

    def test_without_a_topic_alerts_print_instead_of_sending(self):
        with mock.patch.dict(injuries.os.environ, {}, clear=True), mock.patch.object(injuries.requests, "post") as post:
            injuries.notify("t", "b", "u")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
