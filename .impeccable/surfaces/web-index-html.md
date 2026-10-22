---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/src"]
---

# HKX live app

Scope: the live React app (Tonight as the home screen with the card beside it, All markets table, Player out, Ledger with the Paper tab, Rulebook, sign-in). Visitor mode: Operate. Code-led.

Audience and job: Kong and a friend. Pregame on laptop (build and lock tonight's card at Hard Rock prices), breaking news on phone (player out, find teammates' unmoved props in under 2 minutes), during games on phone (follow open bets live), postgame (CLV for the night), weekly rule review, watching the paper trader learn.

Constraints: sport-agnostic shell (league detail only from data); Hard Rock is the only bettable book, edge and stake from its price only; rules hard, blocking rule always named, no overrides; CLV leads every results view; sample data labeled; 1-800-GAMBLER footer; WCAG AA contrast, 11px label floor, keyboard complete; calm, not casino (no confetti, streaks, countdown pressure).

User feedback (2026-10-22): the Games System look read as plain and spreadsheet-like, busy, unappealing colour and type, not like a betting app. User pinned "clean modern sportsbook" at Robinhood's level of polish (the standing exit, taken by the user; no roll).

## Direction contract

THESIS: Every bet is a quote. The desk reads like a clean trading app for props: the player is the ticker, Hard Rock's price is the quote you can take, the fair price is the market, value is the day's change. It refuses the cluttered odds screen and the ink-ruled spreadsheet that came before.

OWN-WORLD: Dark-first for game nights (ground #0e1113, raised #171b1e, line #262c30), a designed light theme (white cards on #f3f5f6). Archivo variable only: UI at normal width, player names and headline figures at wdth 112, weight 800, tabular figures. Rounded 14px cards, pill buttons and quote chips, soft shadow only in light. One mood accent: green when beating the close (or no data), coral when below. League colour appears only as a small dot from data.

STORY: Open on Tonight: a status line that says the machinery is working, live score chips once games tip, then the bets worth taking as quote cards (player, over or under the line, the Hard Rock quote chip, worth, value meter, why). Add, lock into a ticket, place at Hard Rock, follow it live, judge it by the close.

FIRST VIEWPORT: Slim top bar: brand mark and wordmark, league pills (NBA live, others soon), tabs with a mood underline, slate date pill, bankroll and a Beat-the-market chip on the right. Main: large "Tonight" title with games and first tip, status line, score chips, the picks head with Add all, a two-column grid of quote cards. Docked right: Tonight's Card as a raised panel with the risk bar and checks, Lock card as the mood pill. Phones: compact bar, one column of cards, lock bar above a bottom tab bar.

FORM: Clean modern sportsbook at Robinhood polish, pinned by the user (standing exit, no roll). Signature move: the mood accent, every primary action, the active tab and the headline figures turn green or coral with whether the desk is beating the closing line. seed: none (user-pinned direction, no roll was run)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
