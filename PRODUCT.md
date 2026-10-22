# PRODUCT.md — Tip-Off Desk

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: a React + Vite front end, with a small FastAPI server reading the SQLite database (`data/tipoff.db`). This matches the CLAUDE.md roadmap. It was chosen because the interface is the product's differentiator and needs room for rich, precise interaction and motion. The analysis core stays in Python (`tipoff/`). `web/index.html` is the clickable prototype the live front end grows from.

## What it is

A private, locally run NBA betting desk for two friends. Each game day it prices every player prop and game line against a fair line, applies a rulebook, and produces a short card of bets to place at Hard Rock Bet. After the games it grades every bet on the result and on closing-line value (CLV), and the rulebook improves from that evidence.

Claude is the rules clerk and analyst, not the oracle. Nothing reaches the card without a priced edge.

## Positioning

The interface is the differentiator. Betting tools are either cluttered odds screens or hype-driven picks apps. Tip-Off Desk is meant to be beautiful and satisfying to use, a tool its two users want to open. The method underneath is the foundation: bet only when Hard Rock's price beats a de-vigged consensus, grade every bet on CLV, and earn rules through backtests. The satisfaction comes from clarity, speed and craft, never from casino stimulation. Using it well should feel good because it makes the disciplined choice the easy one.

## Brand commitments

- **Look and feel (chosen by Kong, 2026-10-22):** a clean, modern sportsbook at the polish level of Robinhood. Card-based, bold player names, a bright accent, dark-first for game nights with a designed light theme. It replaced the earlier ink-ruled "Games System" look, which read as plain and spreadsheet-like.


Two people: Kong and a friend. Both are comfortable with data and odds, and both use the app on laptops and phones.

- **They know:** American odds, spreads, totals, props, parlays.
- **They're learning:** de-vigging, expected value, Kelly sizing, CLV.
- **They don't need:** onboarding, marketing copy, social features, or a picks marketplace.

## Jobs, in order of frequency

1. **Pregame (daily, ~15 min, laptop):** scan the Edge Board, see which markets clear the rules, build and lock the card.
2. **Breaking news (a few times a week, phone, under 2 min):** a starter is ruled out and props haven't moved yet. See the affected lines and add a bet fast.
3. **Postgame (daily, ~2 min, phone or laptop):** check results and CLV for the night.
4. **Weekly review (~20 min, laptop):** read the backtest and live-results report, then decide which testing rules to promote or retire.

## Operating Context

- Runs on Kong's Windows PC. The data lives in SQLite at `data/tipoff.db`.
- Odds come from paid historical and live odds feeds. Each request costs credits, so data refreshes are deliberate, not continuous.
- Bets are placed by hand in the Hard Rock Bet app. Tip-Off Desk never places bets.
- Game nights run on the NBA schedule. Injury news can land minutes before tip, which is why the breaking-news job is built for speed.
- **Open decision:** how phones and the friend reach the app (same Wi-Fi only, a private network like Tailscale, or hosted with a login). The breaking-news and postgame jobs depend on the answer.

## Capabilities and Constraints

- Prices player props (points, rebounds, assists, threes, blocks) against a fair price taken from a de-vigged market consensus, optionally blended with our own projection via `model_weight`.
- Rules live in `rules.json` with statuses `confirmed`, `testing` and `retired`. Only confirmed rules affect the card, and a status changes only with the users' approval.
- The backtest (`python -m tipoff.backtest`) writes `reports/backtest-*.md`, a JSON version, and `reports/ledger.json`.
- **Multi-sport by design.** The NBA is the first league, used to test the system; other sports will follow. The interface's visual identity must be sport-agnostic. Sport-specific detail (team colors, markets, stat names) comes from data, never from the shell, palette or type.
- **Open decision:** the name "Tip-Off" is basketball language; whether it stays as the sports expand is undecided.
- Terms: Edge Board, Tonight's Card, Rulebook, Ledger & CLV, Game Plan, fair price, edge, CLV, unit, bankroll.
- Not yet built: logging real bets placed, live odds snapshots, an injury watcher, and the live front end.

## Evidence on Hand

- `data/sample.db`: a fake two-season world with deliberately planted edges. Its numbers only show the code works and must never be presented as real results.
- `data/tipoff.db`: real box scores for 2023-24 through 2025-26. No real odds yet, so no real backtest results exist.
- No real betting history, real CLV, or real profit figures exist. Don't fabricate them in UI copy, mockups or empty states; use clearly labeled sample data.

## Product Principles

- **Price before picks.** Every number shown traces back to a fair price. Show the fair line next to every offered price.
- **CLV over win rate.** Lead with CLV wherever results are summarized. Win/loss records are secondary and always shown with sample size.
- **Rules are visible and hard.** When a rule blocks a bet, say which rule and why. No override buttons on the card.
- **Honest numbers.** Show estimated edge and realized CLV side by side. Never show projected profit as if it were certain.
- **Calm, not casino.** No confetti, streak flames, countdown pressure, or "lock of the day" language. The app should make betting less impulsive, not more.
- **Florida reality.** Hard Rock is the book you can bet. Other books appear as price references and are labeled that way.

## Non-goals

- Public picks, social feeds, leaderboards, or sharing to social media.
- Parlay builders (same-game parlays only when a boost makes the priced legs positive EV).
- Real-money automation. The app never places bets.

## Responsible use

Fixed bankroll, nightly risk cap (8% by default), and a stop rule: if CLV is flat or negative after 150 bets, the edge isn't there. Show 1-800-GAMBLER in the footer.
