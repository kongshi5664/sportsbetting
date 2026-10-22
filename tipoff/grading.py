"""Grading: results and closing-line value for locked bets, and for the legs Claude judged.

Reads box scores straight from the database (not the projection cache), so a desk left running
grades last night's games as soon as the morning backfill lands.
"""
from .backtest import _load_snapshot
from .features import MARKET_STAT
from .pricing import consensus, ev, to_american


def close_over(con, settings, event_id, market, key, point):
    """Closing de-vigged probability of the Over at this line, or None without a closing snapshot."""
    close, _ = _load_snapshot(con, event_id, "close")
    books = close.get((market, key, point))
    if not books:
        return None
    targets = set(settings["target_books"])
    return consensus({b: s for b, s in books.items() if b not in targets},
                     sharp=tuple(settings.get("sharp_books", ())), sharp_weight=settings.get("sharp_weight", 0.0))


def game_final(con, event_id):
    """True once the game's team box score is in."""
    return con.execute("SELECT 1 FROM team_games t JOIN events e ON e.game_date=t.game_date AND t.team=e.home_team"
                       " WHERE e.event_id=?", (event_id,)).fetchone() is not None


def box(con, key, date):
    return con.execute("SELECT * FROM player_games WHERE name_key=? AND game_date=?", (key, date)).fetchone()


def outcome(row, market, side, point):
    stat = MARKET_STAT[market]
    if row is None or row[stat] is None:
        return "void", None  # didn't play: the book voids the bet
    actual = row[stat]
    return ("push" if actual == point else ("win" if (actual > point) == (side == "Over") else "loss")), actual


def grade_bets(con, cfg):
    """Grade locked bets whose game is final and has a closing snapshot. Safe to repeat."""
    n = 0
    for b in [dict(r) for r in con.execute("SELECT * FROM bets WHERE status='locked'")]:
        p_over = close_over(con, cfg["settings"], b["event_id"], b["market"], b["name_key"], b["point"])
        if p_over is None or not game_final(con, b["event_id"]):
            continue
        result, actual = outcome(box(con, b["name_key"], b["slate_date"]), b["market"], b["side"], b["point"])
        p_close = p_over if b["side"] == "Over" else 1 - p_over
        con.execute("UPDATE bets SET status='graded', result=?, actual=?, close_price=?, clv=? WHERE id=?",
                    (result, actual, to_american(p_close), None if result == "void" else ev(p_close, b["price"]), b["id"]))
        n += 1
    con.commit()
    return n


def grade_marks(con, cfg):
    """Closing-line value for every prop the paper trader recorded at decision time, bet or not."""
    try:
        rows = con.execute("SELECT slate_date, market_id, price FROM marks WHERE graded=0").fetchall()
    except Exception:
        return 0  # no paper trading yet
    n = 0
    for date, mid, price in rows:
        event_id, market, key, point, side = mid.split("|")
        point = float(point)
        p_over = close_over(con, cfg["settings"], event_id, market, key, point)
        if p_over is None or not game_final(con, event_id):
            continue
        result, _ = outcome(box(con, key, date), market, side, point)
        p_close = p_over if side == "Over" else 1 - p_over
        con.execute("UPDATE marks SET clv=?, result=?, graded=1 WHERE slate_date=? AND market_id=?",
                    (None if result == "void" else ev(p_close, price), result, date, mid))
        n += 1
    con.commit()
    return n


def grade_notes(con, cfg):
    """Closing-line value for every leg Claude judged, bet or not, at the price it saw: this is how
    the review learns whether "skip" calls actually save money."""
    n = 0
    rows = con.execute("SELECT slate_date, market_id, price FROM notes WHERE clv IS NULL AND price IS NOT NULL"
                       " AND graded=0").fetchall()
    for date, mid, price in rows:
        event_id, market, key, point, side = mid.split("|")
        point = float(point)
        p_over = close_over(con, cfg["settings"], event_id, market, key, point)
        if p_over is None or not game_final(con, event_id):
            continue
        result, _ = outcome(box(con, key, date), market, side, point)
        p_close = p_over if side == "Over" else 1 - p_over
        con.execute("UPDATE notes SET clv=?, graded=1 WHERE slate_date=? AND market_id=?",
                    (None if result == "void" else ev(p_close, price), date, mid))
        n += 1
    con.commit()
    return n
