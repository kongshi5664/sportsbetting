---
version: 1
slug: "web-index-html"
primary_target: "web/index.html"
related_targets: ["web/src"]
---

# Tip-Off Desk live app

Scope: the live React app (Edge Board + docked Card, Card, Ledger & CLV, Rulebook, phone Player-out view). Visitor mode: Operate. Code-led.

Audience and job: Kong and a friend. Pregame on laptop (build and lock tonight's card at Hard Rock prices), breaking news on phone (player out, find teammates' unmoved props in under 2 minutes), postgame (CLV for the night), weekly rule review.

Constraints: sport-agnostic shell (league detail only from data); Hard Rock is the only bettable book, edge and stake from its price only; rules hard, blocking rule always named, no overrides; CLV leads every results view; sample data labeled; 1-800-GAMBLER footer; WCAG AA contrast, 11px label floor, keyboard complete.

Critique carry-over (2026-10-16, 19/40): per-leg remove and failing legs named; HR-only pricing; phone stacked board, 44px targets, bottom tabs; Ledger leads with CLV and gates verdicts under 30 bets; lock settles into a ticket.

Unresolved: how phones reach the app; whether the "Tip-Off" name survives multi-sport.

## Direction contract

THESIS: One identity system built to hold every sport, in the tradition of the Munich 1972 Games: a pictogram and a color zone per league on a strict grid. It refuses the category default of a dark odds terminal with green and red numbers.

OWN-WORLD: White ground, ink #1b1d22, flat committed league zones (NBA orange #f28c28; NFL green #3a9a4a, MLB blue #4fa3d8, NHL silver #c7c9c8 waiting). Hanken Grotesk only, tabular figures. 1.5 to 2px ink rules, square corners, no shadows, no gradients. Geometric pictograms on a 45/90 grid. State (pass teal, blocked red, warning ochre) never borrows a league color and always carries a mark or word. A designed dark theme for night use.

STORY: Open the desk, see tonight's priced slate at Hard Rock with the fair price beside every number, add what clears, see exactly why anything is held out, lock the card into a ticket, come back after tip for CLV.

FIRST VIEWPORT: Left pictogram rail (league switcher, NBA live). League-orange header: brand, slate date, tabs Edge Board / Card / Ledger / Rulebook / Player out, bankroll, unit, Avg CLV with n. Main: Edge Board title line with counts and odds snapshot age, filter row, sortable table grouped by game in orange bands, Hard Rock column boxed between ink rules. Docked right: Tonight's Card with legs, risk capacity bar against the nightly cap, named checks, Lock card primary, Clear set apart.

FORM: Games System, my top-ranked grounded candidate (rank 1 of 7) from re-roll round 1, chosen as the pick card. Signature move: the league pictogram rail whose active color runs from the header into the game bands. seed:5a8d844a71db3c8a

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
