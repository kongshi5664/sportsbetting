# Tip-Off Desk

A rules-based NBA player-prop system for two people, run locally. Claude is the rules clerk and analyst, not the oracle: every bet needs a priced edge against a fair line, and every rule has to survive a backtest before it's enforced.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your Odds API key
```

## 1. Try it on fake data (no keys, ~20 seconds)

```bash
python -m tipoff.sample_data                 # builds data/sample.db (two fake seasons)
python -m tipoff.backtest --db data/sample.db
```

The fake world has edges planted on purpose (loose role-player pricing, slow reaction to minutes jumps), so a working harness should flag those rules for promotion. Its numbers mean nothing beyond "the code works".

## 2. Backfill real history

**Box scores (free).** Takes a few minutes per season:

```bash
python -m tipoff.backfill_stats --seasons 2023-24 2024-25 2025-26
```

**Historical prop odds (Odds API paid plan).** Always estimate credits first:

```bash
set -a; source .env; set +a
python -m tipoff.backfill_odds --start 2026-01-05 --end 2026-01-11 --estimate
python -m tipoff.backfill_odds --start 2026-01-05 --end 2026-01-11
```

Each game gets two snapshots: `bet` (60 min before tip, the price you could realistically take) and `close` (5 min before tip, used to grade closing-line value). Start with a few weeks, check the report, then widen.

## 3. Backtest

```bash
python -m tipoff.backtest
```

Writes `reports/backtest-*.md`, a JSON version, and `reports/ledger.json` (every simulated bet, ready for the UI).

What the report tells you:

- **Average CLV** — the number to trust. Positive CLV over hundreds of bets is real edge; results alone are mostly luck at this sample size.
- **Estimated edge vs. CLV** — picking the best few of many lines always overstates the edge. The gap is your haircut.
- **Model vs. market Brier score** — whether our own projection beats the market. If it doesn't, keep `model_weight` low and let price differences do the work.
- **Testing rules** — each one is checked on earlier seasons and again on the held-out latest season, and gets a recommendation: promote, keep testing, or retire. Nothing changes until you edit `rules.json`.

## How it avoids fooling itself

- Projections only use games before the bet date (no look-ahead).
- Bets are priced at a fixed pre-tip snapshot, not the best price of the day.
- Rules must hold up in the held-out season, not just the one they were found in.
- Bankroll sim sizes a whole night from that night's opening bankroll and caps nightly risk.

## Layout

```
tipoff/db.py              SQLite schema + name matching
tipoff/backfill_stats.py  nba_api box scores
tipoff/backfill_odds.py   The Odds API historical props
tipoff/pricing.py         de-vig, EV, Kelly, P(over) from a projection
tipoff/features.py        point-in-time player features and projection
tipoff/backtest.py        rulebook replay, CLV, rule verdicts, ledger
tipoff/sample_data.py     fake two-season world for testing
rules.json                settings + rulebook (statuses: confirmed / testing / retired)
web/index.html            the clickable prototype
```

## Next steps (in Claude Code)

1. Run the real backfills and the first real backtest.
2. Turn `web/index.html` into the live front end reading `reports/ledger.json` and today's odds.
3. Add the live loop: odds snapshots every few minutes on game days, injury-report watcher, and a Claude agent that builds the nightly card under the confirmed rules.

Must be 21+ and in a legal jurisdiction. In Florida, Hard Rock Bet is the regulated sportsbook. Gambling problem? Call 1-800-GAMBLER.
