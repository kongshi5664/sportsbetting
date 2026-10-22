"""Following open bets during the game, from ESPN's live box scores.

    python -m unittest discover tests
"""
import unittest
from unittest import mock

from tipoff import scores

GAME = {"espn_id": "1", "away": "CLE", "home": "PHI", "away_score": 50, "home_score": 48, "state": "in",
        "period": 2, "clock": "0.0", "detail": "Halftime", "elapsed": 24.0}


def bet(id, side, point, stat="pts", key="joelembiid"):
    return {"id": id, "away": "CLE", "home": "PHI", "name_key": key, "stat": stat, "side": side, "point": point}


class ScoresTest(unittest.TestCase):
    def test_elapsed(self):
        self.assertEqual(scores.elapsed(1, "12:00"), 0)
        self.assertAlmostEqual(scores.elapsed(2, "6:00"), 18)
        self.assertAlmostEqual(scores.elapsed(4, "30.0"), 47.5)
        self.assertAlmostEqual(scores.elapsed(5, "2:30"), 50.5)

    def test_track_settles_in_game_and_reads_pace(self):
        box = {"joelembiid": {"dnp": False, "min": 18, "pts": 14, "reb": 3, "ast": 1, "blk": 0, "fg3m": 1}}
        with mock.patch.object(scores, "games", return_value=[GAME]), mock.patch.object(scores, "box", return_value=box):
            out = scores.track("2026-10-22", [bet(1, "Over", 25.5), bet(2, "Over", 12.5), bet(3, "Under", 12.5),
                                              bet(4, "Under", 4.5, "reb")])["bets"]
        self.assertEqual((out["1"]["status"], out["1"]["pace"], out["1"]["on_pace"]), ("live", 28.0, True))
        self.assertEqual(out["2"]["status"], "won", "an over is won once it clears the line")
        self.assertEqual(out["3"]["status"], "lost", "an under is lost once it goes past the line")
        self.assertEqual((out["4"]["status"], out["4"]["on_pace"]), ("live", False))

    def test_unknown_game_or_feed_down(self):
        with mock.patch.object(scores, "games", side_effect=OSError):
            self.assertEqual(scores.track("2026-10-22", [bet(1, "Over", 25.5)]), {"games": [], "bets": {}})


if __name__ == "__main__":
    unittest.main()
