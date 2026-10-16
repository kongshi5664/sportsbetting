"""Generate a FAKE two-season database so the whole pipeline runs before you buy any data.

    python -m tipoff.sample_data          # writes data/sample.db
    python -m tipoff.backtest --db data/sample.db

The fake world has edges planted on purpose, so you can check the harness finds them:
  * Hard Rock prices are noisier than the other books (price-shopping edge).
  * Role players are priced more loosely than stars.
  * Books ignore that bigs rebound less on the second night of a back-to-back.
  * Books are slow to react when a player's minutes jump.
Nothing here is real. Don't read anything into its numbers except "the code works".
"""
import argparse
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .db import connect, name_key
from .pricing import prob_over, to_american

TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
         "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
FIRST = ["Jalen", "Marcus", "Tyrese", "Derrick", "Andre", "Malik", "Isaiah", "Jaylen", "Devin", "Cam", "Keegan", "Josh",
         "Trey", "Aaron", "Bennedict", "Collin", "Dyson", "Evan", "Franz", "Gary", "Herb", "Ivica", "Jonas", "Kel"]
LAST = ["Walker", "Barnes", "Holloway", "Okafor", "Reid", "Sutton", "Price", "Vance", "Moody", "Ellis", "Grant", "Hart",
        "Lowry", "Mercer", "Nash", "Ortiz", "Pruitt", "Quinn", "Rowe", "Sims", "Tate", "Udoka", "Voss", "Wade"]
# role: (pts, reb, ast, fg3m, blk, minutes)
ROLES = [("star", 26, 6, 6, 2.6, 0.6, 35), ("big", 15, 11, 2.5, 0.4, 1.8, 30), ("wing", 17, 5, 3.5, 2.2, 0.5, 32),
         ("guard", 14, 3.5, 6.5, 1.9, 0.3, 30), ("role", 9, 4, 2.2, 1.3, 0.4, 24), ("role", 8, 5.5, 1.5, 0.9, 0.8, 22),
         ("bench", 6, 3, 1.5, 0.8, 0.3, 16), ("bench", 5, 3.5, 1, 0.5, 0.5, 14), ("bench", 4, 2, 1, 0.5, 0.2, 10)]
STATS = ("pts", "reb", "ast", "fg3m", "blk")
MARKETS = {"pts": "player_points", "reb": "player_rebounds", "ast": "player_assists", "fg3m": "player_threes", "blk": "player_blocks"}
BOOKS = {"draftkings": 0.012, "fanduel": 0.012, "betmgm": 0.015, "hardrockbet": 0.022}  # price noise per book (win-prob points)


def draw(rng, mu, stat):
    if stat == "pts":
        return max(0, round(rng.gauss(mu, 0.32 * mu + 1.5)))
    # gamma-poisson mixture = negative binomial (over-dispersed counts)
    lam = rng.gammavariate(6, mu / 6) if mu > 0 else 0
    k, p, L = 0, 1.0, pow(2.718281828, -lam)
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def price_pair(rng, p_over, vig, noise):
    p = min(0.85, max(0.15, p_over + rng.gauss(0, noise)))
    over, under = p * (1 + vig / 2), (1 - p) * (1 + vig / 2)
    return to_american(over), to_american(under)


def season_dates(start_year):
    d, end = date(start_year, 10, 22), date(start_year + 1, 4, 12)
    while d <= end:
        yield d
        d += timedelta(days=1)


def generate(path, seed=7):
    rng = random.Random(seed)
    Path(path).unlink(missing_ok=True)
    con = connect(path)
    players, pid = {}, 1
    used = set()
    for t in TEAMS:
        roster = []
        for role in ROLES:
            while True:
                nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if nm not in used:
                    used.add(nm)
                    break
            scale = rng.uniform(0.85, 1.15)
            roster.append({"id": pid, "name": nm, "role": role[0], "base": dict(zip(STATS, [v * scale for v in role[1:6]])),
                           "min": role[6], "prop": role[0] != "bench"})
            pid += 1
        players[t] = roster

    for start_year in (2024, 2025):
        season = f"{start_year}-{(start_year + 1) % 100:02d}"
        defense = {t: {s: rng.uniform(0.92, 1.08) for s in ("pts", "reb", "ast")} for t in TEAMS}
        last_played = {t: None for t in TEAMS}
        games_played = {p["id"]: 0 for t in TEAMS for p in players[t]}
        # minutes jumps: ~1 in 5 role/bench players gets a bigger role partway through the season
        spike = {p["id"]: rng.randint(20, 70) for t in TEAMS for p in players[t] if p["role"] in ("role", "wing") and rng.random() < 0.3}
        recent = {p["id"]: [] for t in TEAMS for p in players[t]}
        for d in season_dates(start_year):
            if d.month == 2 and 14 <= d.day <= 20:
                continue  # All-Star break
            pool = TEAMS[:]
            rng.shuffle(pool)
            rest_ok = [t for t in pool if last_played[t] != d - timedelta(days=1) or rng.random() < 0.35]
            today = rest_ok[: 2 * rng.randint(4, 6)]
            for i in range(0, len(today) - 1, 2):
                home, away = today[i], today[i + 1]
                gid = f"{season[:4]}{d.strftime('%m%d')}{home}{away}"
                tip = datetime(d.year, d.month, d.day, 23, 30, tzinfo=timezone.utc)
                eid = f"ev_{gid}"
                con.execute("INSERT INTO events VALUES (?,?,?,?,?)", (eid, tip.isoformat().replace("+00:00", "Z"), str(d), home, away))
                team_tot = {}
                odds_rows = []
                for team, opp, is_home in ((home, away, 1), (away, home, 0)):
                    b2b = last_played[team] == d - timedelta(days=1)
                    tot = {"pts": 0, "reb": 0, "ast": 0}
                    for p in players[team]:
                        gp = games_played[p["id"]]
                        boost = 1.3 if p["id"] in spike and gp >= spike[p["id"]] else 1.0
                        mins = p["min"] * boost * rng.uniform(0.85, 1.12)
                        true_mu = {}
                        for s in STATS:
                            mu = p["base"][s] * boost * (defense[opp][s] if s in defense[opp] else 1)
                            if s == "reb" and b2b and p["role"] == "big":
                                mu *= 0.84  # planted edge: books don't price this
                            true_mu[s] = mu
                        line = {s: draw(rng, true_mu[s], s) for s in STATS}
                        con.execute("INSERT INTO player_games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                    (season, gid, str(d), p["id"], p["name"], name_key(p["name"]), team, opp, is_home,
                                     round(mins, 1), line["pts"], line["reb"], line["ast"], line["blk"],
                                     rng.randint(0, 2), line["fg3m"], rng.randint(0, 4)))
                        for s in ("pts", "reb", "ast"):
                            tot[s] += line[s]
                        if p["prop"] and gp >= 3:
                            hist = recent[p["id"]]
                            for s in STATS:
                                if s in ("fg3m", "blk") and p["base"][s] < 0.9:
                                    continue
                                # The books' estimate: season form, slow to see minutes jumps, blind to b2b for bigs.
                                lagged = sum(h[s] for h in hist[-15:]) / len(hist[-15:]) if hist else p["base"][s]
                                book_mu = 0.5 * lagged + 0.5 * p["base"][s] * (defense[opp].get(s, 1))
                                book_mu *= 1.0 if p["role"] in ("star", "big") else rng.uniform(0.94, 1.06)  # stars priced tighter
                                pt = max(0.5, round(book_mu * 2) / 2)
                                if pt.is_integer():
                                    pt += 0.5
                                sd = 0.32 * book_mu + 1.5 if s == "pts" else (book_mu * 1.4) ** 0.5
                                p_book, _ = prob_over(pt, book_mu, sd, s)
                                p_true, _ = prob_over(pt, true_mu[s], 0.32 * true_mu[s] + 1.5 if s == "pts" else (true_mu[s] * 1.4) ** 0.5, s)
                                p_close = 0.45 * p_book + 0.55 * p_true  # the market learns before tip
                                for label, pp, ts in (("bet", p_book, tip - timedelta(minutes=60)), ("close", p_close, tip - timedelta(minutes=5))):
                                    for book, noise in BOOKS.items():
                                        o, u = price_pair(rng, pp, 0.045, noise if label == "bet" else noise / 2)
                                        iso = ts.isoformat().replace("+00:00", "Z")
                                        odds_rows.append((eid, label, iso, book, MARKETS[s], p["name"], name_key(p["name"]), "Over", pt, o))
                                        odds_rows.append((eid, label, iso, book, MARKETS[s], p["name"], name_key(p["name"]), "Under", pt, u))
                        hist_row = {s: line[s] for s in STATS}
                        recent[p["id"]].append(hist_row)
                        games_played[p["id"]] += 1
                    team_tot[team] = tot
                    last_played[team] = d
                con.executemany("INSERT INTO prop_odds VALUES (?,?,?,?,?,?,?,?,?,?)", odds_rows)
                for team, opp, is_home in ((home, away, 1), (away, home, 0)):
                    con.execute("INSERT INTO team_games VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (season, gid, str(d), team, opp, is_home, team_tot[team]["pts"], team_tot[opp]["pts"],
                                 team_tot[team]["reb"], team_tot[team]["ast"]))
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM events WHERE game_date LIKE ?", (f"{start_year}-1%",)).fetchone()[0]
        print(f"{season}: generated (sample)")
    con.close()
    print(f"Wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "sample.db"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    generate(a.out, a.seed)
