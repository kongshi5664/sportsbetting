"""Price one slate for the live desk: the backtest's math at a single snapshot, without results.

The fair price comes only from the reference books (Hard Rock excluded), blended with our
projection by model_weight. Edge and stake always use the Hard Rock price, the only one we
can actually bet.
"""
from datetime import datetime, timezone

from .backtest import _load_snapshot, _rule_matches
from .features import MARKET_STAT
from .pricing import consensus, devig_pair, ev, kelly_stake, prob_over, to_american, to_decimal

STAT_LABEL = {"pts": "Points", "reb": "Rebounds", "ast": "Assists", "fg3m": "Threes", "blk": "Blocks"}


def rule_params(rules, rid, key, default):
    r = next((r for r in rules if r["id"] == rid), None)
    return r.get("params", {}).get(key, default) if r else default


def slate_dates(con):
    return [r[0] for r in con.execute("SELECT DISTINCT game_date FROM events ORDER BY game_date DESC")]


def price_slate(con, fs, cfg, date, card=()):
    """All priced markets on `date`, grouped by game. `card` is the list of open bets (dicts with
    name_key, market, event_id, side, point) so the per-player and per-night caps can be shown."""
    settings, rules = cfg["settings"], cfg["rules"]
    targets = set(settings["target_books"])
    w = settings["model_weight"]
    bankroll = settings["bankroll"]
    min_edge = rule_params(rules, "min_edge", "min", 0.02)
    per_player = rule_params(rules, "max_per_player", "max", 2)
    per_night = rule_params(rules, "max_per_night", "max", 12)
    avoid = [r for r in rules if r["status"] == "confirmed" and r["kind"] == "avoid"]
    testing = [r for r in rules if r["status"] == "testing"]

    card_ids = {_bet_id(b) for b in card}
    legs_by_player = {}
    for b in card:
        legs_by_player[b["name_key"]] = legs_by_player.get(b["name_key"], 0) + 1

    games = []
    for e in con.execute("SELECT * FROM events WHERE game_date=? ORDER BY commence_time", (date,)):
        # The latest live snapshot when there is one; otherwise the backfilled 'bet' snapshot.
        label = "live" if con.execute("SELECT 1 FROM prop_odds WHERE event_id=? AND label='live' LIMIT 1",
                                      (e["event_id"],)).fetchone() else "bet"
        lines, names = _load_snapshot(con, e["event_id"], label)
        snap = con.execute("SELECT MAX(snapshot_ts) FROM prop_odds WHERE event_id=? AND label=?",
                           (e["event_id"], label)).fetchone()[0]
        best = {}
        for (market, key, point), books in lines.items():
            stat = MARKET_STAT.get(market)
            refs = {b: s for b, s in books.items() if b not in targets}
            p_mkt_over = consensus(refs)
            f = fs.player(key, date, stat) if stat else None
            if p_mkt_over is None or f is None:
                continue  # no reference price to de-vig, or too little history to project
            p_over, p_push = prob_over(point, f["proj"], f["sd"], stat)
            for side in ("Over", "Under"):
                offers = [(s[side], b) for b, s in books.items() if b in targets and side in s]
                if not offers:
                    continue
                price, book = max(offers, key=lambda o: to_decimal(o[0]))
                p_mkt = p_mkt_over if side == "Over" else 1 - p_mkt_over
                p_model = (p_over if side == "Over" else 1 - p_over - p_push) / max(1e-9, 1 - p_push)
                fair = w * p_model + (1 - w) * p_mkt
                m = {
                    "id": f"{e['event_id']}|{market}|{key}|{point:g}|{side}",
                    "event_id": e["event_id"], "market": market, "stat": stat, "stat_label": STAT_LABEL[stat],
                    "player": names.get(key, key), "name_key": key, "team": f["team"],
                    "side": side, "point": point, "book": book, "price": price,
                    "fair": fair, "fair_american": to_american(fair), "edge": ev(fair, price),
                    "stake": round(kelly_stake(fair, price, bankroll, settings["kelly_fraction"],
                                               settings["stake_cap_units"]), 2),
                    "refs": {b: s.get(side) for b, s in refs.items()},
                    "proof": {
                        "books": {b: {"over": s.get("Over"), "under": s.get("Under"),
                                      "p_over": round(devig_pair(s["Over"], s["Under"])[0], 4)}
                                  for b, s in refs.items() if "Over" in s and "Under" in s},
                        "p_market": round(p_mkt, 4), "p_model": round(p_model, 4), "model_weight": w,
                        "projection": round(f["proj"], 2),
                    },
                    "f": f,
                }
                pk = (key, market)
                if pk not in best or m["edge"] > best[pk]["edge"]:
                    best[pk] = m
        markets = sorted(best.values(), key=lambda m: -m["edge"])
        for m in markets:
            m["on_card"] = m["id"] in card_ids
            m["flags"] = _flags(m, min_edge, per_player, per_night, avoid, testing, legs_by_player, len(card))
            m["blocked"] = any(fl["blocks"] for fl in m["flags"])
            m.pop("f")
        games.append({
            "event_id": e["event_id"], "away": e["away_team"], "home": e["home_team"],
            "commence_time": e["commence_time"], "snapshot_ts": snap, "snapshot": label, "markets": markets,
        })
    return games


def _flags(m, min_edge, per_player, per_night, avoid, testing, legs_by_player, n_card):
    b = {"f": m["f"], "stat": m["stat"], "side": m["side"], "p_model": m["proof"]["p_model"]}
    flags = []
    if m["edge"] < min_edge:
        flags.append({"rule": "min_edge", "text": f"HR edge below {min_edge:.0%}", "blocks": True})
    for r in avoid:
        if _rule_matches(r, b):
            flags.append({"rule": r["id"], "text": r["name"], "blocks": True})
    if not m["on_card"]:
        if legs_by_player.get(m["name_key"], 0) >= per_player:
            flags.append({"rule": "max_per_player", "text": f"Player cap · {per_player} per player", "blocks": True})
        if n_card >= per_night:
            flags.append({"rule": "max_per_night", "text": f"Card full · {per_night} per night", "blocks": True})
    for r in testing:
        if _rule_matches(r, b):
            flags.append({"rule": r["id"], "text": r["name"], "blocks": False, "testing": True})
    return flags


def suggest(games, card, cfg):
    """Tonight's suggested additions to the card: every unblocked market, biggest Hard Rock edge
    first, kept within the confirmed caps and the night's remaining risk. A spread rule
    (settings.suggest_max_per_game) keeps the card from riding on one game's pace or blowout.
    Suggestions are only ever drawn from priced edges; nothing here adds a bet the price doesn't."""
    settings, rules = cfg["settings"], cfg["rules"]
    per_player = rule_params(rules, "max_per_player", "max", 2)
    per_night = rule_params(rules, "max_per_night", "max", 12)
    per_game = settings.get("suggest_max_per_game", 3)
    room = settings.get("nightly_risk_cap", 0.08) * settings["bankroll"] - sum(b["stake"] for b in card)
    players, events = {}, {}
    for b in card:
        players[b["name_key"]] = players.get(b["name_key"], 0) + 1
        events[b["event_id"]] = events.get(b["event_id"], 0) + 1
    picks, n = [], len(card)
    pool = sorted((m for g in games for m in g["markets"] if not m["blocked"] and not m["on_card"]),
                  key=lambda m: -m["edge"])
    for m in pool:
        if n >= per_night:
            break
        if players.get(m["name_key"], 0) >= per_player or events.get(m["event_id"], 0) >= per_game:
            continue
        if m["stake"] > room + 1e-9:
            continue
        picks.append(m)
        room -= m["stake"]
        n += 1
        players[m["name_key"]] = players.get(m["name_key"], 0) + 1
        events[m["event_id"]] = events.get(m["event_id"], 0) + 1
    return picks


def _bet_id(b):
    return f"{b['event_id']}|{b['market']}|{b['name_key']}|{b['point']:g}|{b['side']}"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
