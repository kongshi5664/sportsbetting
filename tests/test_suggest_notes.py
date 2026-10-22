"""The suggested card and Claude's notes, without network calls.

    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tipoff import notes
from tipoff.board import suggest
from tipoff.db import connect

CFG = {
    "settings": {"bankroll": 2000, "nightly_risk_cap": 0.08, "suggest_max_per_game": 2},
    "rules": [{"id": "max_per_player", "kind": "gate", "status": "confirmed", "params": {"max": 1}},
              {"id": "max_per_night", "kind": "gate", "status": "confirmed", "params": {"max": 12}}],
}


def m(i, edge, stake, event="g1", player=None, blocked=False, on_card=False):
    return {"id": f"m{i}", "edge": edge, "stake": stake, "event_id": event, "name_key": player or f"p{i}",
            "blocked": blocked, "on_card": on_card}


class SuggestTest(unittest.TestCase):
    def test_best_edges_within_caps(self):
        games = [{"markets": [m(1, 0.09, 40), m(2, 0.08, 40), m(3, 0.07, 40),  # g1: only two fit
                              m(4, 0.06, 40, player="p1"),                    # second leg for p1
                              m(5, 0.20, 40, blocked=True)]},                 # held out by a rule
                 {"markets": [m(6, 0.05, 40, event="g2"), m(7, 0.04, 40, event="g2")]}]
        picks = [p["id"] for p in suggest(games, [], CFG)]
        self.assertEqual(picks, ["m1", "m2", "m6", "m7"])

    def test_respects_remaining_risk(self):
        card = [{"stake": 150, "name_key": "x", "event_id": "g9"}]
        games = [{"markets": [m(1, 0.09, 40), m(2, 0.08, 9)]}]
        self.assertEqual([p["id"] for p in suggest(games, card, CFG)], ["m2"])  # $10 of room left


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = connect(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_no_key_is_a_clear_message(self):
        with mock.patch.dict(notes.os.environ, {}, clear=True), mock.patch.object(notes, "load_env"):
            with self.assertRaisesRegex(notes.NotesError, "ANTHROPIC_API_KEY"):
                notes.ask_claude([{"id": "a"}], "2026-10-20")

    def test_parses_and_keeps_only_known_legs(self):
        body = {"notes": [{"id": "a", "verdict": "caution", "note": "Listed questionable (ankle).", "sources": ["u"]},
                          {"id": "zzz", "verdict": "skip", "note": "not a leg we sent", "sources": []}]}
        resp = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(body))])
        client = mock.MagicMock()
        client.beta.messages.create.return_value = resp
        with mock.patch.dict(notes.os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch.object(notes.anthropic, "Anthropic", return_value=client):
            out = notes.ask_claude([{"id": "a"}], "2026-10-20")
        self.assertEqual(list(out), ["a"])
        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["fallbacks"], "default")
        notes.save(self.con, "2026-10-20", out)
        self.assertEqual(notes.load(self.con, "2026-10-20")["a"]["verdict"], "caution")

    def test_refusal_is_reported_not_crashed(self):
        resp = SimpleNamespace(stop_reason="refusal", content=[])
        client = mock.MagicMock()
        client.beta.messages.create.return_value = resp
        with mock.patch.dict(notes.os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch.object(notes.anthropic, "Anthropic", return_value=client):
            with self.assertRaisesRegex(notes.NotesError, "declined"):
                notes.ask_claude([{"id": "a"}], "2026-10-20")


if __name__ == "__main__":
    unittest.main()
