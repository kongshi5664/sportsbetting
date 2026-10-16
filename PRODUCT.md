# PRODUCT.md — Tip-Off Desk

## What it is

A private, locally run NBA betting desk for two friends. Each game day it prices every player prop and game line against a fair line, applies a rulebook, and produces a short card of bets to place at Hard Rock Bet. After the games it grades every bet on the result and on closing-line value (CLV), and the rulebook improves from that evidence.

Claude is the rules clerk and analyst, not the oracle. Nothing reaches the card without a priced edge.

## Users

Two people: Kong and a friend. Both are comfortable with data and odds, and both use the app on laptops and phones.

- **They know:** American odds, spreads, totals, props, parlays.
- **They're learning:** de-vigging, expected value, Kelly sizing, CLV.
- **They don't need:** onboarding, marketing copy, social features, or a picks marketplace.

## Jobs, in order of frequency

1. **Pregame (daily, ~15 min, laptop):** scan the Edge Board, see which markets clear the rules, build and lock the card.
2. **Breaking news (a few times a week, phone, under 2 min):** a starter is ruled out and props haven't moved yet. See the affected lines and add a bet fast.
3. **Postgame (daily, ~2 min, phone or laptop):** check results and CLV for the night.
4. **Weekly review (~20 min, laptop):** read the backtest and live-results report, then decide which testing rules to promote or retire.

## Principles

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
