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

## 4. Run the desk

```bash
cd web && npm install && npm run build && cd ..   # once, and after front-end changes
python -m tipoff.api --db data/sample.db          # open http://127.0.0.1:8000
```

Without `--db` it reads `data/tipoff.db`. The board prices the latest slate in the database (pick another with the date in the header). Add markets that clear the rulebook, lock the card, then place each leg by hand in Hard Rock Bet and tick it off. Locked bets are graded on the Ledger once the game's box score and closing prices are in.

For front-end work, run the API as above and `npm run dev` in `web/` (http://localhost:5173, proxies `/api`).

## 5. Live odds on game days

Put your key in `.env` (`ODDS_API_KEY=...`). Live calls work on The Odds API's free tier: each game costs about 5 credits per refresh (5 prop markets, our books count as one region), and listing the night's games is free.

```bash
python -m tipoff.snapshot --estimate              # tonight's games and the cost of one refresh; spends nothing
python -m tipoff.snapshot --watch --every 30      # refresh every 30 min, take each game's close 5 min before tip
```

`--watch` stops by itself after the last tip and won't pass `--max-credits` (600 by default) in one run. The desk also has a **Refresh odds** button on tonight's board for breaking news. To run it unattended, point Windows Task Scheduler at `.venv\Scripts\python.exe -m tipoff.snapshot --watch --every 30` with the project folder as "Start in", daily around 3pm.

First night: compare a few props against the Hard Rock app. The Odds API lists `hardrockbet` as its Indiana feed ("same odds as several other states"), so confirm Florida matches before trusting it.

## 6. Suggested card and Claude's notes

The card panel suggests tonight's legs: every market that clears the rules, biggest Hard Rock edge first, at most `suggest_max_per_game` legs from one game (`rules.json` settings), within the night's risk cap. **Add all** takes them in one tap.

With `ANTHROPIC_API_KEY` in `.env`, **Check news with Claude** sends the card and suggested legs to Claude (Opus 5.5 with web search). It looks for injury, lineup and minutes news and marks each leg *clear*, *caution* or *skip* with a one-line reason and its sources. Notes are advice: they never add a bet or override a rule, and **Add all** leaves out any leg Claude flagged *skip* (you can still add it by hand). Each check costs roughly $0.10–0.30. From the terminal: `python -m tipoff.notes --date 2026-10-20`.

## 7. Game days in one double-click

- `scripts\morning-odds.bat`: loads last night's box scores (free; grading and projections need them), then one odds pull for today's games; it becomes the **opening line**, and the desk shows when Hard Rock has moved since. Schedule it around 10am in Windows Task Scheduler (Start in: this folder).
- `scripts\game-day.bat`: starts the desk, the odds watcher (every 30 minutes, closing prices just before each tip) and the injury watcher (every 3 minutes), then opens Tonight. The watchers stop after the last tip.

**Injury alerts** (`python -m tipoff.injuries --watch`): ESPN's public injury feed, checked every few minutes; when a player with props tonight changes status, you get an alert saying what changed, whether they're on your card, and a link to Player out, and that game's odds are re-pulled (about 5 credits). For phone alerts, install the free **ntfy** app, subscribe to a private topic name, and set `NTFY_TOPIC` in `.env`; without it, alerts print in the watcher window.

## 8. Learning from the bets: the weekly review

Every bet stores what was true when you took it (player features, the prices, whether Pinnacle priced it, the testing rules it matched), and every leg Claude judged stores the price it saw. Once games are final, the desk grades both against the closing line.

The **Rulebook** opens with *This week's review* (also `scripts\weekly-review.bat`, which writes `reports/review-DATE.md`):

- **Rules**: does each testing rule's group of bets beat the close by more (or less) than the rest? Clear evidence becomes a proposal to promote, retire, or move a confirmed rule back to testing.
- **Settings**: are 2–3% value bets losing to the close (propose a 3% minimum)? Do Pinnacle-priced bets beat the close more (lean on it more or less)?
- **Claude's calls**: did the legs Claude flagged *skip* actually do worse against the close than the ones it cleared?

It judges by closing-line value, never wins and losses; a proposal needs 30+ graded bets on each side of a comparison and a gap about two standard errors clear of the noise. Nothing changes until you press **Apply** (with a confirm), and every decision is logged.

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
tipoff/board.py           prices one slate for the live desk (Hard Rock edge vs. fair)
tipoff/api.py             FastAPI server: slate, card, ledger, rulebook, player-out, refresh
tipoff/snapshot.py        live odds snapshots (refresh, close, watch)
tipoff/notes.py           Claude's news check on each leg (clear / caution / skip)
tipoff/injuries.py        injury watcher and phone alerts (ESPN feed, ntfy)
tipoff/grading.py         results and closing-line value for bets and Claude's calls
tipoff/review.py          weekly review: rules, settings, Claude's calls; proposals you apply
scripts/                  morning-odds.bat, game-day.bat, weekly-review.bat
tests/                    python -m unittest discover tests
web/                      the live desk (React + Vite); web/prototype.html is the old mock
```

## Next steps (in Claude Code)

1. Run the real backfills and the first real backtest.
2. ~~Turn the prototype into the live front end~~ (done: `web/` + `tipoff/api.py`).
3. Add the live loop: odds snapshots every few minutes on game days, injury-report watcher, and a Claude agent that builds the nightly card under the confirmed rules.

Must be 21+ and in a legal jurisdiction. In Florida, Hard Rock Bet is the regulated sportsbook. Gambling problem? Call 1-800-GAMBLER.
