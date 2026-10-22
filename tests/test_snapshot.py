"""Live snapshots without spending credits: The Odds API is replaced by canned payloads.

    python -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tipoff import snapshot as live
from tipoff.board import price_slate
from tipoff.db import connect
from tipoff.features import FeatureStore

# Keep the fake credit counts below out of the real data/status.json.
os.environ["TIPOFF_STATUS"] = str(Path(tempfile.mkdtemp()) / "status.json")

ROOT = Path(__file__).resolve().parent.parent


def _event(minutes_to_tip):
    tip = datetime.now(timezone.utc) + timedelta(minutes=minutes_to_tip)
    return {"id": "abc123", "commence_time": tip.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": "Detroit Pistons", "away_team": "San Antonio Spurs"}


def _odds(point, hr_over=105):
    def book(key, over, under):
        return {"key": key, "markets": [{"key": "player_blocks", "outcomes": [
            {"name": "Over", "description": "Victor Wembanyama", "price": over, "point": point},
            {"name": "Under", "description": "Victor Wembanyama", "price": under, "point": point}]}]}
    return {"bookmakers": [book("hardrockbet", hr_over, -125), book("draftkings", -110, -110),
                           book("fanduel", -108, -112), book("betmgm", -112, -108)]}


class Resp:
    def __init__(self, body, cost):
        self.body, self.status_code = body, 200
        self.headers = {"x-requests-last": str(cost), "x-requests-remaining": "480"}

    def json(self):
        return self.body

    def raise_for_status(self):
        pass


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.tmp.name) / "t.db")
        # Enough history for a projection: the board skips players with fewer than five games.
        for i in range(10):
            d = (datetime.now(live.ET).date() - timedelta(days=12 - i)).isoformat()
            self.con.execute("INSERT INTO player_games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             ("2026-27", f"g{i}", d, 1, "Victor Wembanyama", "victorwembanyama", "SAS", "DET",
                              1, 32.0, 24, 11, 3, 3 + i % 3, 1, 2, 3))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def fake(self, point):
        def get(url, params=None, timeout=None):
            if url.endswith("/events"):
                return Resp([_event(90)], 0)
            return Resp(_odds(point), 5)
        return get

    def test_parse_and_team_codes(self):
        rows = live.odds_rows("abc123", "live", "2026-10-21T22:00:00Z", _odds(3.5))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0][6], "victorwembanyama")
        self.assertEqual(live.team_code("San Antonio Spurs"), "SAS")

    def test_refresh_replaces_moved_lines(self):
        today = datetime.now(live.ET).date()
        with mock.patch.object(live.requests, "get", self.fake(3.5)):
            live.refresh(self.con, today, "k", live.Credits())
        with mock.patch.object(live.requests, "get", self.fake(4.5)):
            credits = live.Credits()
            live.refresh(self.con, today, "k", credits)
        points = {r[0] for r in self.con.execute("SELECT point FROM prop_odds WHERE label='live'")}
        self.assertEqual(points, {4.5}, "the old 3.5 line must not linger after the book moves it")
        self.assertEqual(credits.used, 5)
        self.assertEqual(credits.remaining, 480)
        ev = self.con.execute("SELECT home_team, away_team FROM events").fetchone()
        self.assertEqual(tuple(ev), ("DET", "SAS"))

    def test_credit_limit_stops_refresh(self):
        with mock.patch.object(live.requests, "get", self.fake(3.5)):
            n = live.refresh(self.con, datetime.now(live.ET).date(), "k", live.Credits(), max_credits=4)
        self.assertEqual(n, 0)

    def test_board_prices_live_snapshot(self):
        today = datetime.now(live.ET).date()
        with mock.patch.object(live.requests, "get", self.fake(3.5)):
            live.refresh(self.con, today, "k", live.Credits())
        cfg = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
        games = price_slate(self.con, FeatureStore(self.con), cfg, today.isoformat())
        self.assertEqual(games[0]["snapshot"], "live")
        m = games[0]["markets"][0]
        self.assertEqual((m["book"], m["price"]), ("hardrockbet", 105))
        self.assertNotIn("hardrockbet", m["refs"], "Hard Rock must never feed its own fair price")


if __name__ == "__main__":
    unittest.main()
