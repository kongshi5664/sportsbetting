"""NFL support: league config, features without look-ahead, odds parsing, pricing, live box scores,
grading, the paper trader's journal and review, and the desk's league switch. No network calls:
The Odds API, ESPN and nflverse are all replaced by canned data.

    python -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault("TIPOFF_STATUS", str(Path(tempfile.mkdtemp()) / "status.json"))

from tipoff import backfill_nfl, grading, journal, leagues, review, scores  # noqa: E402
from tipoff import snapshot as live  # noqa: E402
from tipoff.board import price_slate  # noqa: E402
from tipoff.db import connect  # noqa: E402
from tipoff.features import FeatureStore  # noqa: E402
from tipoff.leagues import NBA, NFL  # noqa: E402
from tipoff.pricing import prob_over  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NFL_CFG = json.loads((ROOT / "rules.nfl.json").read_text(encoding="utf-8"))


def add_game(con, d, key="jamarrchase", name="Ja'Marr Chase", team="CIN", opp="PIT", season="2026",
             rec_yds=80, rec=6, home=1, gid=None):
    con.execute("INSERT INTO player_games (season, game_id, game_date, player_id, player_name, name_key, team, opponent,"
                " home, minutes, position, pass_yds, pass_att, pass_cmp, rush_yds, rush_att, rec_yds, rec, targets)"
                " VALUES (?,?,?,?,?,?,?,?,?,NULL,'WR',0,0,0,0,0,?,?,?)",
                (season, gid or f"{d}_{team}", d, "00-1", name, key, team, opp, home, rec_yds, rec, rec + 2))


def add_team_game(con, d, team, opp, rec_yds=230, gid=None):
    con.execute("INSERT INTO team_games (season, game_id, game_date, team, opponent, home, pts, opp_pts, pass_yds,"
                " pass_att, rush_yds, rush_att, rec_yds, rec) VALUES ('2026',?,?,?,?,1,20,17,?,34,110,26,?,22)",
                (gid or f"{d}_{team}", d, team, opp, rec_yds, rec_yds))


def weekly(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=7 * i)).isoformat() for i in range(n)]


class TempDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.con = connect(Path(self.tmp.name) / "nfl.db", league="nfl", check_same_thread=False)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class LeagueConfigTest(unittest.TestCase):
    def test_nba_config_reproduces_the_old_constants(self):
        from tipoff import board, features
        self.assertEqual(features.MARKET_STAT, {"player_points": "pts", "player_rebounds": "reb",
                                                "player_assists": "ast", "player_threes": "fg3m",
                                                "player_blocks": "blk"})
        self.assertEqual(board.STAT_LABEL["fg3m"], "Threes")
        self.assertEqual(live.DEFAULT_MARKETS, ["player_points", "player_rebounds", "player_assists",
                                                "player_threes", "player_blocks"])
        self.assertEqual(live.team_code("LA Clippers"), "LAC")
        self.assertEqual(NBA.db_file, "tipoff.db")

    def test_nfl_markets_are_the_six_over_unders(self):
        self.assertEqual(NFL.sport_key, "americanfootball_nfl")
        self.assertEqual(set(NFL.market_stat.values()), {"pass_yds", "pass_att", "rush_yds", "rush_att", "rec_yds", "rec"})
        self.assertFalse(any("td" in m for m in NFL.markets), "touchdown props are Yes-only and can't be de-vigged")
        self.assertEqual(len(NFL.team_codes), 32)
        self.assertEqual(leagues.stat_of("player_reception_yds"), "rec_yds")
        self.assertEqual(leagues.stat_of("player_points"), "pts")

    def test_stat_keys_are_unique_across_leagues(self):
        self.assertFalse(set(NBA.stat_label) & set(NFL.stat_label))
        self.assertFalse(set(NBA.market_stat) & set(NFL.market_stat))

    def test_separate_databases(self):
        self.assertEqual(NFL.db_path.name, "nfl.db")
        self.assertEqual(NFL.rules_path.name, "rules.nfl.json")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            con = connect(Path(d) / "x.db", league="nfl")
            cols = {r[1] for r in con.execute("PRAGMA table_info(player_games)")}
            self.assertTrue({"pass_yds", "rush_att", "rec", "targets"} <= cols)
            for t in ("events", "prop_odds", "bets"):
                self.assertTrue(con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone())
            con.close()


class FeaturesTest(TempDB):
    def test_no_look_ahead(self):
        """Features on a date are identical whether or not that day's and later games are in the
        database: nothing from the game being bet (or after it) can leak in."""
        dates = weekly("2026-09-10", 8)
        for i, d in enumerate(dates):
            add_game(self.con, d, rec_yds=40 + 10 * i, rec=3 + i % 4)
            add_team_game(self.con, d, "PIT", "CIN", rec_yds=200 + 5 * i)
            add_team_game(self.con, d, "BAL", "PIT", rec_yds=260)
        self.con.commit()
        bet_day = dates[5]
        full = FeatureStore(self.con, "nfl").player("jamarrchase", bet_day, "rec_yds")
        self.con.execute("DELETE FROM player_games WHERE game_date > ?", (bet_day,))
        self.con.execute("DELETE FROM team_games WHERE game_date >= ?", (bet_day,))
        self.con.execute("UPDATE player_games SET rec_yds=999, rec=99 WHERE game_date=?", (bet_day,))
        self.con.commit()
        cut = FeatureStore(self.con, "nfl").player("jamarrchase", bet_day, "rec_yds")
        self.assertEqual(full, cut)
        self.assertAlmostEqual(full["mean10"], sum(40 + 10 * i for i in range(5)) / 5)
        self.assertEqual(full["games_played"], 5)

    def test_short_history_windows_and_nba_only_features(self):
        dates = weekly("2026-09-10", 3)
        for i, d in enumerate(dates):
            add_game(self.con, d, rec_yds=60 + i)
        self.con.commit()
        fs = FeatureStore(self.con, "nfl")
        self.assertIsNone(fs.player("jamarrchase", dates[2], "rec_yds"), "two games is too little history")
        f = fs.player("jamarrchase", "2026-10-01", "rec_yds")
        self.assertIsNotNone(f, "three games of history are enough in the NFL")
        self.assertIsNone(f["b2b"])
        self.assertIsNone(f["min_trend"])
        self.assertIsNone(f["season_pts"])

    def test_recent_window_is_six_games(self):
        for i, d in enumerate(weekly("2026-09-10", 10)):
            add_game(self.con, d, rec_yds=0 if i < 4 else 100)
        self.con.commit()
        f = FeatureStore(self.con, "nfl").player("jamarrchase", "2026-11-30", "rec_yds")
        self.assertEqual(f["mean10"], 100.0, "only the last six games count as recent form")


class PricingTest(unittest.TestCase):
    def test_yards_use_a_normal(self):
        p, push = prob_over(64.5, 64.5, 30.0, "rec_yds")
        self.assertAlmostEqual(p, 0.5, places=6)
        self.assertEqual(push, 0.0)
        self.assertGreater(prob_over(54.5, 64.5, 30.0, "rec_yds")[0], prob_over(74.5, 64.5, 30.0, "rec_yds")[0])

    def test_yards_sd_floor(self):
        # A tiny sample sd can't make a receiver look like a sure thing: the floor is 60% of the mean.
        p, _ = prob_over(70.5, 60.0, 1.0, "rec_yds")
        self.assertGreater(p, 0.35)
        p_qb, _ = prob_over(260.5, 250.0, 5.0, "pass_yds")
        self.assertGreater(p_qb, 0.4)

    def test_counts_use_negative_binomial(self):
        p, push = prob_over(5.5, 5.5, 2.8, "rec")
        self.assertTrue(0.35 < p < 0.6)
        self.assertEqual(push, 0.0)
        p, push = prob_over(5.0, 5.5, 2.8, "rec")
        self.assertGreater(push, 0.05, "a whole-number line can push on a count")
        p_att, _ = prob_over(33.5, 35.0, 6.0, "pass_att")
        self.assertTrue(0.5 < p_att < 0.75)

    def test_nba_points_math_unchanged(self):
        import math
        mu, sd, line = 20.0, 3.0, 22.5
        sd_used = max(sd, 0.35 * mu, 2.0)
        want = 1 - 0.5 * (1 + math.erf((line - mu) / sd_used / math.sqrt(2)))
        self.assertAlmostEqual(prob_over(line, mu, sd, "pts")[0], want, places=12)


def nfl_event(minutes_to_kick=90):
    kick = datetime.now(timezone.utc) + timedelta(minutes=minutes_to_kick)
    return {"id": "nfl1", "commence_time": kick.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": "Los Angeles Rams", "away_team": "Washington Commanders"}


def nfl_odds(point=64.5, hr_over=110):
    def book(key, over, under, markets=("player_reception_yds", "player_receptions")):
        out = []
        for mk in markets:
            pt = point if mk == "player_reception_yds" else 5.5
            out.append({"key": mk, "outcomes": [
                {"name": "Over", "description": "Puka Nacua", "price": over, "point": pt},
                {"name": "Under", "description": "Puka Nacua", "price": under, "point": pt}]})
        return {"key": key, "markets": out}
    return {"bookmakers": [book("hardrockbet", hr_over, -140), book("draftkings", -110, -110),
                           book("pinnacle", -108, -112), book("fanduel", -112, -108)]}


class Resp:
    def __init__(self, body, cost=0):
        self.body, self.status_code = body, 200
        self.headers = {"x-requests-last": str(cost), "x-requests-remaining": "400"}
        self.text = ""

    def json(self):
        return self.body

    def raise_for_status(self):
        pass


class OddsTest(TempDB):
    def setUp(self):
        super().setUp()
        today = datetime.now(live.ET).date()
        for i in range(6):
            d = (today - timedelta(days=7 * (6 - i))).isoformat()
            add_game(self.con, d, key="pukanacua", name="Puka Nacua", team="LA", opp="SF", rec_yds=60 + 4 * i, rec=6)
        self.con.commit()
        self.urls = []

    def fake(self, url, params=None, timeout=None):
        self.urls.append(url)
        if url.endswith("/events"):
            return Resp([nfl_event()])
        return Resp(nfl_odds(), 6)

    def test_parse_and_team_codes(self):
        rows = live.odds_rows("nfl1", "live", "2026-10-25T16:00:00Z", nfl_odds())
        self.assertEqual(len(rows), 16)
        self.assertEqual({r[4] for r in rows}, {"player_reception_yds", "player_receptions"})
        self.assertEqual(rows[0][6], "pukanacua")
        self.assertEqual(live.team_code("Los Angeles Rams", "nfl"), "LA")
        self.assertEqual(live.team_code("Washington Commanders", "nfl"), "WAS")
        self.assertEqual(live.team_code("Los Angeles Rams", "nfl"), NFL.team_codes["Los Angeles Rams"])

    def test_refresh_hits_the_nfl_endpoint_and_prices_the_board(self):
        today = datetime.now(live.ET).date()
        credits = live.Credits()
        with mock.patch.object(live.requests, "get", self.fake):
            n = live.refresh(self.con, today, "k", credits, league="nfl")
        self.assertEqual(n, 1)
        self.assertTrue(all("/sports/americanfootball_nfl/" in u for u in self.urls))
        self.assertEqual(tuple(self.con.execute("SELECT home_team, away_team FROM events").fetchone()), ("LA", "WAS"))
        games = price_slate(self.con, FeatureStore(self.con, "nfl"), NFL_CFG, today.isoformat())
        ms = games[0]["markets"]
        self.assertEqual({m["stat_label"] for m in ms}, {"Receiving yards", "Receptions"})
        m = next(m for m in ms if m["stat"] == "rec_yds")
        self.assertEqual((m["book"], m["side"], m["price"]), ("hardrockbet", "Over", 110))
        self.assertNotIn("hardrockbet", m["refs"])
        self.assertFalse(m["blocked"], "+110 against a -110 market clears the 2% bar")
        self.assertEqual(m["team"], "LA")

    def test_default_markets_cost_six_credits(self):
        params = {}

        def get(url, params=None, timeout=None):
            if url.endswith("/odds"):
                seen.update(params)
            return self.fake(url, params, timeout)
        seen = params
        with mock.patch.object(live.requests, "get", get):
            live.refresh(self.con, datetime.now(live.ET).date(), "k", live.Credits(), league="nfl")
        self.assertEqual(seen["markets"].split(","), list(NFL.markets))
        self.assertEqual(seen["bookmakers"].split(","), live.DEFAULT_BOOKS)


def espn_summary():
    def blk(name, keys, athletes):
        return {"name": name, "keys": keys, "athletes": [{"athlete": {"displayName": n}, "stats": s} for n, s in athletes]}
    return {"boxscore": {"players": [{"team": {"abbreviation": "LAR"}, "statistics": [
        blk("passing", ["completions/passingAttempts", "passingYards", "yardsPerPassAttempt"],
            [("Matthew Stafford", ["21/30", "245", "8.2"])]),
        blk("rushing", ["rushingAttempts", "rushingYards"], [("Kyren Williams", ["18", "77"]),
                                                             ("Matthew Stafford", ["2", "-3"])]),
        blk("receiving", ["receptions", "receivingYards", "receivingTargets"],
            [("Puka Nacua", ["7", "88", "9"]), ("Kyren Williams", ["2", "11", "3"])]),
        blk("defensive", ["totalTackles"], [("Some Linebacker", ["9"])]),
    ]}]}}


class LiveScoresTest(unittest.TestCase):
    def test_football_box_merges_categories(self):
        with mock.patch.object(scores, "_get", return_value=espn_summary()):
            b = scores.box("1", "nfl")
        self.assertEqual((b["matthewstafford"]["pass_att"], b["matthewstafford"]["pass_yds"]), (30.0, 245.0))
        self.assertEqual(b["matthewstafford"]["rush_yds"], -3.0, "negative rushing yards stay negative")
        self.assertEqual((b["kyrenwilliams"]["rush_att"], b["kyrenwilliams"]["rec"]), (18.0, 2.0))
        self.assertEqual((b["pukanacua"]["rec"], b["pukanacua"]["rec_yds"]), (7.0, 88.0))
        self.assertIsNone(b["pukanacua"]["min"])

    def test_clock_is_fifteen_minute_quarters(self):
        self.assertEqual(scores.elapsed(1, "15:00", "nfl"), 0)
        self.assertAlmostEqual(scores.elapsed(2, "7:30", "nfl"), 22.5)
        self.assertAlmostEqual(scores.elapsed(5, "5:00", "nfl"), 65.0)
        self.assertAlmostEqual(scores.elapsed(4, "30.0"), 47.5, msg="NBA clock unchanged")

    def test_espn_codes_and_track(self):
        board = {"events": [{"id": "9", "status": {"period": 2, "displayClock": "0:00",
                                                   "type": {"state": "in", "shortDetail": "Halftime"}},
                             "competitions": [{"competitors": [
                                 {"homeAway": "home", "team": {"abbreviation": "LAR"}, "score": "14"},
                                 {"homeAway": "away", "team": {"abbreviation": "WSH"}, "score": "10"}]}]}]}
        with mock.patch.object(scores, "_get", side_effect=lambda path, params, league=None:
                               board if path == "scoreboard" else espn_summary()):
            out = scores.track("2026-10-25", [
                {"id": 1, "away": "WAS", "home": "LA", "name_key": "pukanacua", "stat": "rec_yds", "side": "Over",
                 "point": 64.5},
                {"id": 2, "away": "WAS", "home": "LA", "name_key": "kyrenwilliams", "stat": "rush_yds",
                 "side": "Over", "point": 160.5}], "nfl")
        g = out["games"][0]
        self.assertEqual((g["home"], g["away"], g["elapsed"]), ("LA", "WAS", 30.0))
        self.assertEqual(out["bets"]["1"]["status"], "won")
        self.assertEqual((out["bets"]["2"]["pace"], out["bets"]["2"]["on_pace"]), (154.0, False))


class GradingTest(TempDB):
    def test_nfl_bet_grades_from_player_games(self):
        self.con.execute("INSERT INTO events VALUES ('nfl1','2026-10-25T20:25:00Z','2026-10-25','LA','WAS')")
        add_game(self.con, "2026-10-25", key="pukanacua", name="Puka Nacua", team="LA", opp="WAS", rec_yds=88, rec=7)
        add_team_game(self.con, "2026-10-25", "LA", "WAS")
        for book, o, u in (("draftkings", -130, 110), ("pinnacle", -125, 105), ("hardrockbet", -120, 100)):
            for side, price in (("Over", o), ("Under", u)):
                self.con.execute("INSERT INTO prop_odds VALUES ('nfl1','close','t',?, 'player_reception_yds',"
                                 " 'Puka Nacua','pukanacua',?,64.5,?)", (book, side, price))
        self.con.execute("INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price,"
                         " fair, edge, stake, added_at, status, paper, strategy) VALUES ('2026-10-25','nfl1',"
                         "'player_reception_yds','pukanacua','Puka Nacua','Over',64.5,'hardrockbet',110,0.5,0.05,"
                         "50,'t','locked',1,'current')")
        self.con.commit()
        self.assertEqual(grading.grade_bets(self.con, NFL_CFG), 1)
        r = self.con.execute("SELECT result, actual, clv FROM bets").fetchone()
        self.assertEqual((r["result"], r["actual"]), ("win", 88))
        self.assertGreater(r["clv"], 0, "the market closed past -110 on the over we took at +110")


class BackfillTest(unittest.TestCase):
    GAMES = [{"game_id": "2026_07_WAS_LA", "gameday": "2026-10-25", "home_team": "LA", "away_team": "WAS",
              "home_score": "27", "away_score": "20"}]

    def player(self, name, pid, pos, team="LA", opp="WAS", gid="2026_07_WAS_LA", **stats):
        row = {"player_id": pid, "player_display_name": name, "position": pos, "team": team, "opponent_team": opp,
               "game_id": gid, "week": "7", "attempts": "0", "carries": "0", "targets": "0"}
        row.update({k: str(v) for k, v in stats.items()})
        return row

    def test_rows_dates_and_dropped_defense(self):
        games = backfill_nfl.schedule(self.GAMES)
        rows, unplaced = backfill_nfl.player_rows([
            self.player("Puka Nacua", "00-1", "WR", receptions=7, receiving_yards=88, targets=9),
            self.player("Some Linebacker", "00-2", "LB", team="WAS", opp="LA"),
            self.player("Lost Row", "00-3", "RB", gid="2026_07_XXX_YYY", carries=5),
        ], games, 2026)
        self.assertEqual(len(rows), 1, "defenders without offensive touches are left out")
        r = rows[0]
        self.assertEqual((r[0], r[2], r[5], r[6], r[7], r[8]), ("2026", "2026-10-25", "pukanacua", "LA", "WAS", 1))
        self.assertEqual((r[10], r[12], r[16:]), ("WR", 0, (88, 7, 9)))  # position, pass att, rec yds/rec/targets
        self.assertEqual([u["player_display_name"] for u in unplaced], ["Lost Row"], "unmatched games are reported")

    def test_name_collisions_are_reported(self):
        games = backfill_nfl.schedule(self.GAMES)
        rows, _ = backfill_nfl.player_rows([self.player("Josh Allen", "00-1", "QB", attempts=30),
                                            self.player("Josh Allen", "00-9", "TE", targets=2)], games, 2026)
        self.assertIn("joshallen", backfill_nfl.name_collisions(rows))

    def test_backfill_loads_players_and_teams(self):
        team = {"team": "LA", "opponent_team": "WAS", "game_id": "2026_07_WAS_LA", "passing_yards": "245",
                "attempts": "30", "rushing_yards": "110", "carries": "25", "receiving_yards": "245",
                "receptions": "21"}

        def fetch(url):
            if url == backfill_nfl.GAMES:
                return self.GAMES
            if "stats_player" in url:
                return [self.player("Puka Nacua", "00-1", "WR", receptions=7, receiving_yards=88, targets=9)]
            return [team]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = backfill_nfl.backfill(["2026"], Path(d) / "nfl.db", fetch=fetch)
            self.assertEqual(out, [("2026", 1, 1)])
            con = connect(Path(d) / "nfl.db", league="nfl")
            t = con.execute("SELECT pts, opp_pts, rec_yds FROM team_games").fetchone()
            self.assertEqual(tuple(t), (27, 20, 245))
            con.close()


DAY = "2026-10-25"


def paper_bet(con, strategy, result, market="player_reception_yds", price=110, stake=50, clv=0.04, actual=88):
    con.execute("INSERT INTO bets (slate_date, event_id, market, name_key, player, side, point, book, price, fair, edge,"
                " stake, added_at, status, result, clv, actual, paper, strategy, context)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                (DAY, "nfl1", market, "pukanacua", "Puka Nacua", "Over", 64.5, "hardrockbet", price, 0.5, 0.05,
                 stake, "t", "graded" if result else "locked", result, clv, actual, strategy,
                 json.dumps({"f": {"games_played": 6, "opp_factor": 1.0}, "stat": "rec_yds", "side": "Over",
                             "p_model": 0.55, "p_market": 0.5, "sharp": True})))


class JournalReviewTest(TempDB):
    def test_decision_entry_uses_nfl_words(self):
        m = {"id": "nfl1|player_reception_yds|pukanacua|64.5|Over", "player": "Puka Nacua", "side": "Over",
             "point": 64.5, "stat_label": "Receiving yards", "stake": 50.0, "price": 110, "fair_american": -105,
             "edge": 0.07, "flags": []}
        journal.decision_entry(self.con, DAY, [{"away": "WAS", "home": "LA"}], {"current": [m]}, [m], {}, 0.02)
        e = journal.entries(self.con)[0]
        self.assertIn("WAS @ LA: 1 paper bet", e["title"])
        self.assertIn("Puka Nacua OVER 64.5 receiving yards", e["body"])

    def test_recap_numbers_and_label(self):
        self.con.execute("INSERT INTO events VALUES ('nfl1','2026-10-25T20:25:00Z',?,'LA','WAS')", (DAY,))
        paper_bet(self.con, "current", "win", price=110, stake=50)                       # +55
        paper_bet(self.con, "current", "loss", market="player_receptions", stake=20)    # -20
        self.con.execute("CREATE TABLE IF NOT EXISTS marks (slate_date TEXT, market_id TEXT, event_id TEXT, player TEXT,"
                         " stat TEXT, side TEXT, price INTEGER, p_market REAL, p_model REAL, n_refs INTEGER,"
                         " context TEXT, decided_at TEXT, clv REAL, result TEXT, graded INTEGER)")
        self.con.execute("INSERT INTO marks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                         (DAY, "m1", "nfl1", "Puka Nacua", "rec_yds", "Over", 110, 0.5, 0.5, 3, "{}", "t", 0.03, "win"))
        self.con.commit()
        nums = journal.night_numbers(self.con, DAY)
        cur = nums["strategies"][0]
        self.assertEqual((cur["profit"], cur["wins"], cur["losses"]), (35.0, 1, 1))
        self.assertIn("receptions", cur["bet_list"][1]["bet"])
        self.assertIn("receiving yards", nums["all_props"]["by_stat"])
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("tipoff.injuries.notify") as push:
            title, text = journal.recap(self.con, DAY, league="nfl")
        self.assertTrue(title.startswith("NFL Sunday: +$35"), title)
        self.assertEqual(push.call_args[0][3], "football")
        self.assertIn("+$35.00", text)

    def test_recap_skips_days_without_nfl_games(self):
        with mock.patch("tipoff.injuries.notify") as push:
            title, _ = journal.recap(self.con, "2026-10-21", league="nfl")
        self.assertIsNone(title)
        push.assert_not_called()
        self.assertEqual(journal.entries(self.con), [])

    def test_catch_up_waits_for_every_bet_to_be_graded(self):
        paper_bet(self.con, "current", "win")
        paper_bet(self.con, "current", None)  # Sunday's late game: box score not in yet
        self.con.commit()
        self.assertEqual(journal.days_to_recap(self.con, "2026-10-27"), [])
        self.con.execute("UPDATE bets SET status='graded', result='loss'")
        self.con.commit()
        self.assertEqual(journal.days_to_recap(self.con, "2026-10-27"), [DAY])
        journal.add(self.con, DAY, "recap", "t", "b")
        self.assertEqual(journal.days_to_recap(self.con, "2026-10-27"), [], "each game day is recapped once")

    def test_review_findings_by_nfl_stat_and_strategy(self):
        self.con.execute("CREATE TABLE IF NOT EXISTS marks (slate_date TEXT, market_id TEXT, event_id TEXT, player TEXT,"
                         " stat TEXT, side TEXT, price INTEGER, p_market REAL, p_model REAL, n_refs INTEGER,"
                         " context TEXT, decided_at TEXT, clv REAL, result TEXT, graded INTEGER)")
        for i in range(40):
            stat = ("rec_yds", "pass_att")[i % 2]
            self.con.execute("INSERT INTO marks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                             (DAY, f"m{i}", "nfl1", "P", stat, ("Over", "Under")[i % 2], 110, 0.5, 0.5, 3, "{}", "t",
                              0.02 if stat == "rec_yds" else -0.01, "win"))
        for i in range(35):
            paper_bet(self.con, "current", "win", clv=0.01 + (i % 5) * 0.001)
            paper_bet(self.con, "min3", "win", clv=0.06 + (i % 5) * 0.001)
        self.con.commit()
        rep = review.run(self.con, NFL_CFG)
        by_id = {f["id"]: f for f in rep["findings"]}
        stat_groups = dict(by_id["marks:stat"]["groups"])
        self.assertEqual(set(stat_groups), {"Receiving yards", "Pass attempts"})
        self.assertEqual(stat_groups["Receiving yards"]["n"], 20)
        strat = by_id["paper:strategies"]
        self.assertEqual(strat["proposal"]["strategy"], "min3", "a clearly better strategy is proposed, not applied")
        self.assertEqual(json.loads((ROOT / "rules.nfl.json").read_text(encoding="utf-8")), NFL_CFG)
        rule_ids = {f["id"] for f in rep["findings"] if f["area"] == "rule"}
        self.assertEqual(rule_ids, {"rule:skip_early_season", "rule:model_disagrees", "rule:soft_matchup_over"})


class RulesFileTest(unittest.TestCase):
    def test_nfl_rules_mirror_nba_gates_and_drop_nba_only_rules(self):
        nba = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
        gates = lambda c: {r["id"]: r["params"] for r in c["rules"] if r["kind"] == "gate"}
        self.assertEqual(gates(NFL_CFG), gates(nba))
        self.assertEqual(NFL_CFG["settings"]["bankroll"], 15000)
        ids = {r["id"] for r in NFL_CFG["rules"]}
        self.assertFalse(ids & {"b2b_big_reb_over", "minutes_spike", "role_player_props"})
        from tipoff.backtest import _rule_matches
        f = {"games_played": 2, "opp_factor": 1.05, "b2b": None, "min_trend": None, "season_pts": None}
        for r in NFL_CFG["rules"]:
            if r["kind"] != "gate":
                _rule_matches(r, {"f": f, "stat": "rec_yds", "side": "Over", "p_model": 0.4})  # no KeyError/TypeError


class ApiLeagueTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from tipoff import api
        self.api = api
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.nba = connect(Path(self.tmp.name) / "nba.db", check_same_thread=False)
        self.nfl = connect(Path(self.tmp.name) / "nfl.db", league="nfl", check_same_thread=False)
        self.nba.execute("INSERT INTO events VALUES ('nba1','2026-10-22T23:00:00Z','2026-10-22','PHI','CLE')")
        self.nfl.execute("INSERT INTO events VALUES ('nfl1','2026-10-25T17:00:00Z','2026-10-25','LA','WAS')")
        paper_bet(self.nfl, "current", None)
        self.nba.commit()
        self.nfl.commit()
        p = mock.patch.dict(api._state, {"con": self.nba, "con:nfl": self.nfl})
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("TIPOFF_PASSWORD", None)
        self.c = TestClient(api.app, client=("127.0.0.1", 5000))

    def tearDown(self):
        self.nba.close()
        self.nfl.close()
        self.tmp.cleanup()

    def test_default_stays_nba(self):
        m = self.c.get("/api/meta").json()
        self.assertEqual((m["league"], m["dates"][-1], m["markets"]), ("nba", "2026-10-22", 5))
        self.assertTrue(next(l for l in m["leagues"] if l["id"] == "nfl")["live"])

    def test_header_routes_to_the_nfl_database(self):
        m = self.c.get("/api/meta", headers={"X-League": "nfl"}).json()
        self.assertEqual((m["league"], m["dates"][-1], m["markets"]), ("nfl", "2026-10-25", 6))
        self.assertEqual(m["stat_labels"]["rec_yds"], "Receiving yards")
        self.assertEqual(m["settings"]["bankroll"], 15000)
        q = self.c.get("/api/meta", params={"league": "nfl"}).json()
        self.assertEqual(q["league"], "nfl")

    def test_paper_ledger_follows_the_league(self):
        with mock.patch("tipoff.api.grade"):
            nfl = self.c.get("/api/ledger", params={"source": "paper"}, headers={"X-League": "nfl"}).json()
            nba = self.c.get("/api/ledger", params={"source": "paper"}).json()
        self.assertEqual([w["bet"] for w in nfl["waiting"]], ["Puka Nacua · Receiving yards O 64.5"])
        self.assertEqual(nba["waiting"], [])

    def test_threaded_endpoint_sees_the_league(self):
        from tipoff import status
        status.update(nfl_trader_at=status.now(), nfl_trader_day="2026-10-25")
        nfl = self.c.get("/api/status", params={"date": "2026-10-25"}, headers={"X-League": "nfl"}).json()
        nba = self.c.get("/api/status", params={"date": "2026-10-25"}).json()
        self.assertTrue(nfl["trader"]["running"])
        self.assertEqual(nfl["games"], 1)
        self.assertEqual(nba["games"], 0)

    def test_unknown_or_unreleased_league_is_refused(self):
        self.assertEqual(self.c.get("/api/meta", headers={"X-League": "mlb"}).status_code, 400)
        self.assertEqual(self.c.get("/api/meta", headers={"X-League": "cricket"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
