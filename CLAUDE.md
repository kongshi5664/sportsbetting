# CLAUDE.md — Tip-Off Desk

NBA player-prop betting system for Kong and a friend, run locally. Read README.md for commands.

## Principles (don't break these)

- **Price, not picks.** A bet exists only when the offered price beats a fair price derived from a de-vigged market consensus (optionally blended with our projection via `model_weight`). Never add bets based on narrative.
- **CLV is the scoreboard.** Every bet must store the price taken and the closing price. Judge rules and changes by CLV, not win rate.
- **No look-ahead.** Anything in `features.py` or new feature code may only use data timestamped before the bet snapshot. Add a test when adding a feature.
- **Rules are data, enforced by code.** `rules.json` holds statuses and params; predicates live in `_rule_matches` in `backtest.py`. Only `confirmed` rules affect the card. Never change a rule's status without the user's approval; propose changes with the backtest numbers.
- **Target book is Hard Rock** (`hardrockbet`), the regulated Florida sportsbook. Other books are price references for the consensus.

## Conventions

- Python 3.11+, standard library plus requests/pandas/nba_api. SQLite at `data/tipoff.db` (`data/sample.db` for fake data).
- Odds API historical calls cost credits: always support and run `--estimate` before a backfill, and keep requests narrow.
- Player names are matched across sources with `db.name_key`; log and fix mismatches rather than dropping them silently.
- Reports go in `reports/`; don't commit `data/` or `reports/`.

## Roadmap

1. Real backfill + first backtest; review rule verdicts with the user.
2. Live front end from `web/index.html` (React/Vite) reading the DB via a small FastAPI server.
3. Live loop: scheduled odds snapshots, injury watcher with phone alerts, Claude agent (tool use) that builds the nightly card and writes a one-line reason per leg.
4. Weekly review: Claude reads graded bets and proposes rule promotions/retirements.
