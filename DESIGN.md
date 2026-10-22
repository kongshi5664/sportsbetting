---
name: HKX
description: A clean trading-app desk for player props, where every bet is a quote and one mood accent tells you whether the desk is beating the close.
colors:
  bg: "#f2f4f5"
  card: "#ffffff"
  sunk: "#f2f4f5"
  ink: "#0f1417"
  ink-2: "#48535a"
  mute: "#66717a"
  line: "#e4e8ea"
  line-2: "#d2d8db"
  sil: "#b9c1c5"
  up: "#06733f"
  up-fill: "#077a45"
  up-soft: "#e2f5eb"
  down: "#b8311c"
  down-fill: "#d43c25"
  down-soft: "#fce9e5"
  warn: "#855600"
  warn-soft: "#fbf0d6"
  focus: "#2563eb"
  on-mood: "#ffffff"
  bg-dark: "#0e1113"
  card-dark: "#171b1e"
  sunk-dark: "#1e2327"
  ink-dark: "#f2f5f6"
  ink-2-dark: "#b3bcc1"
  mute-dark: "#8d979d"
  line-dark: "#262d31"
  line-2-dark: "#343c41"
  sil-dark: "#4b555b"
  up-dark: "#34d687"
  up-fill-dark: "#2fd583"
  up-soft-dark: "#11301f"
  down-dark: "#ff7a66"
  down-fill-dark: "#ff6b55"
  down-soft-dark: "#3b1b16"
  warn-dark: "#f2b84b"
  warn-soft-dark: "#33280f"
  focus-dark: "#7aa7ff"
  on-mood-dark: "#05150c"
  league-nba: "#f28c28"
  league-nfl: "#3a9a4a"
  league-mlb: "#4fa3d8"
  league-nhl: "#9aa3a8"
  series-1: "#2a78d6"
  series-2: "#eb6834"
  series-3: "#1baf7a"
  series-4: "#c98500"
  series-1-dark: "#3987e5"
  series-2-dark: "#d95926"
  series-3-dark: "#199e70"
typography:
  display:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
    fontVariation: "'wdth' 112"
  headline:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
    fontVariation: "'wdth' 112"
  title:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.015em"
    fontVariation: "'wdth' 112"
  quote:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: 1.15
    fontFeature: "tnum"
    fontVariation: "'wdth' 112"
  body:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  nav:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
  label:
    fontFamily: "Archivo Variable, Archivo, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  sm: "10px"
  chip: "12px"
  card: "14px"
  sheet: "20px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  card: "18px"
  gutter: "24px"
  page: "28px"
components:
  button-primary:
    backgroundColor: "{colors.up-fill}"
    textColor: "{colors.on-mood}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.sunk}"
  button-soft:
    backgroundColor: "{colors.up-soft}"
    textColor: "{colors.up}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
    height: "36px"
  button-lock:
    backgroundColor: "{colors.up-fill}"
    textColor: "{colors.on-mood}"
    rounded: "{rounded.pill}"
    padding: "12px"
    height: "48px"
  league-pill:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "32px"
  pill-ok:
    backgroundColor: "{colors.up-soft}"
    textColor: "{colors.up}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  pill-no:
    backgroundColor: "{colors.down-soft}"
    textColor: "{colors.down}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  pill-warn:
    backgroundColor: "{colors.warn-soft}"
    textColor: "{colors.warn}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
  quote-chip-hard-rock:
    backgroundColor: "{colors.up-soft}"
    textColor: "{colors.up}"
    typography: "{typography.quote}"
    rounded: "{rounded.chip}"
    padding: "8px 12px"
  quote-chip:
    backgroundColor: "{colors.sunk}"
    textColor: "{colors.ink}"
    rounded: "{rounded.chip}"
    padding: "8px 12px"
  card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.card}"
    padding: "18px"
  input-field:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
    height: "36px"
  tab-bar-item-active:
    backgroundColor: "{colors.up-soft}"
    textColor: "{colors.up}"
    rounded: "{rounded.chip}"
    height: "48px"
---

# Design System: HKX

## Overview

**Creative North Star: "Every Bet Is a Quote"**

The desk reads like a clean trading app for player props. The player is the ticker, Hard Rock's price is the quote you can take, the fair price is what it is worth, and value is the day's change. Surfaces are rounded raised panels on a quiet ground; controls are pills; one typeface, Archivo, does all the work, opening up to a wider stretch for the names and figures that matter. The look was pinned by the user as a clean modern sportsbook at Robinhood's level of polish, and it replaces the ink-ruled "Games System" entirely.

The single expressive device is the mood accent. Every primary action, the active tab, the brand mark, the card's risk bar and the headline quote chip share one accent that is green while the desk is beating the closing line (or has no record yet) and coral when it is not. The rest of the interface stays neutral so that the accent carries meaning, not decoration.

Density is a calm desk, not an odds screen: two columns of quote cards beside a docked card panel on laptops, one column with a lock bar and a bottom tab bar on phones. Both themes are designed; the app follows the system setting until the user picks one, and game nights are expected to run dark.

**Key Characteristics:**
- One mood accent (green up, coral down) drives every primary action and headline figure.
- Archivo variable only; names and figures at width 112, weight 800, tabular numerals everywhere.
- Rounded raised panels (14px) and pill controls; soft shadow in light, none in dark.
- League colour appears only as a small dot.
- Calm motion: short, eased state changes; nothing celebratory.

## Colors

A cool neutral desk with one switchable mood accent, a warning amber, and a sport palette confined to dots.

### Primary
- **Beating-the-Close Green** (up-fill / up): the mood accent while CLV is flat or positive. Fills primary buttons, the Lock card pill, the active-tab underline, the count badge, the brand mark, the risk bar, checkbox accents and the toast dot. The deeper text value is used for accent-coloured text on its soft tint (the Hard Rock quote chip, the Beat-the-market chip, the soft Add button).
- **Below-the-Close Coral** (down-fill / down): the same role when the desk's average CLV is negative (`data-mood="down"` on the root swaps it in). It is also the error/blocked hue: failed legs, "no" pills, danger buttons, the remove-leg hover.
- **Mood tints** (up-soft, down-soft): the soft ground behind accent text: quote chip, mood chip, on-card board rows, locked-ticket head, mobile active tab.

### Tertiary
- **Ledger Amber** (warn / warn-soft): notices, the SAMPLE tag, injury lines, questionable-status pills. Never used as an accent for action.
- **Focus Blue** (focus): the 2.5px focus outline only.

### Neutral
- **Desk Ground** (bg): the page ground. In light it equals sunk, so raised white cards do the separating.
- **Panel** (card): every raised surface: quote cards, the docked card, tables, filters, controls.
- **Sunk** (sunk): inset wells inside panels: secondary quote chips, segmented-control track, game rows in tables, the "Show the math" drawer, hover rows.
- **Ink / Ink 2 / Mute** (ink, ink-2, mute): primary text, secondary text, and labels/meta respectively.
- **Line / Line 2 / Silver** (line, line-2, sil): hairline dividers and card borders; control borders; inactive meter segments and scrollbars.

### Data colours
- **League dots** (league-nba, league-nfl, league-mlb, league-nhl): 7-8px dots on league pills, game rows, quote-card headers and team lists. Never a fill, never a border.
- **Strategy series** (series-1 to series-4, control in mute dashed): the paper-strategies chart. Colour follows the strategy, never its rank.

### Named Rules
**The Mood Rule.** There is one accent, and it means something: green while the desk beats the close, coral when it does not. Every primary action, the active tab and the headline quote take it; nothing else gets a second accent.

**The Dot Rule.** Sport colour enters only as a small dot fed by data. The shell, palette and type stay sport-agnostic.

**The Tint-Not-Fill Rule.** Status and accent text sit on their own soft tint (up-soft, down-soft, warn-soft) rather than on a saturated fill; saturated fills are reserved for the primary action.

## Typography

**Display Font:** Archivo Variable (with Archivo, system-ui, sans-serif)
**Body Font:** Archivo Variable, same family
**Label Font:** Archivo Variable, same family

**Character:** One grotesque in two widths. UI text sits at normal width; player names, page titles and figures open to width 112 at weight 800, which gives the quote a ticker-board presence without a second family. Tabular numerals are on for the whole body.

### Hierarchy
- **Display** (800, 64px, 1.0, -0.03em, wdth 112): the night's results figure; the ledger's lead CLV figure runs at 60px. Drops to 48/46px on phones.
- **Headline** (800, 34px, 1.1, -0.02em, wdth 112): page titles ("Sun, Apr 12"), and the card's risk figure. 28px on phones.
- **Title** (800, 24px, 1.1, -0.015em, wdth 112): player names on quote cards and section heads (picks head, out head, calm panels). 21-22px on phones. Smaller titles step through 20px (journal, rule groups), 19px (Tonight's Card) and 18px (journal entries).
- **Quote** (800, 26px, 1.15, wdth 112): Hard Rock's price in the quote chip; Worth and Bet beside it at 17px. Board prices at 16px.
- **Body** (400, 14px, 1.45): running text; 13px for supporting lines; prose capped at 60-76ch.
- **Nav** (700, 15px): desktop tabs; buttons and controls at 700, 13px.
- **Label** (600-700, 11-12px): quote-chip labels, stat labels, meta. Table column headers and status badges (SAMPLE, WIN/LOSS) use 11px, 700, 0.04em, uppercase. 11px is the floor.

### Named Rules
**The Two Widths Rule.** Names and figures at width 112, everything else at 100. A wide setting on body copy, or a second family, breaks the ticker.

**The Tabular Rule.** Every number is set in tabular figures so prices, stakes and scores align in columns and do not jitter when they update.

## Layout

A centred desk with a 1360px maximum and 28px side padding (16px on phones). Tonight and All markets are two-column grids: main content plus a 352px docked card (300px between 1181 and 1320px; 24-28px gap). The docked card is sticky at 132px from the top. Quote cards flow in an auto-fill grid with a 320px minimum and 16px gaps, forced to two columns at 1180px and one at 860px.

The top bar is sticky and translucent (88% ground with a 14px backdrop blur), 64px tall, holding the brand, league pills, slate date pill, stats and theme toggle; tabs sit in a 46px row beneath it. Below 1180px the dock folds under the main column, secondary stats hide and only the mood chip stays. Below 860px the tabs and league pills leave the top bar for a fixed, blurred bottom tab bar of five 48px targets, a floating lock bar sits above it, and board rows restack into a three-area grid (who/price/add, market/value/add, rules).

Spacing runs on a 4px base: 4, 8, 12, 16, 18 (panel inner padding), 24 and 28 (gutters and page padding). Breakpoints: 1500px (reference-book column and rule-pill compaction), 1320px, 1180px, 860px.

## Elevation & Depth

A hybrid: raised panels in light, tonal layering in dark. In light, every panel carries the same soft two-layer shadow plus a 1px line border; lifted states (hovered quote card, tooltip, sign-in, toast, lock bar) take a stronger shadow. In dark, the resting shadow is removed entirely and panels separate by surface value (ground, card, sunk), with only lifted elements keeping a deep shadow.

### Shadow Vocabulary
- **Rest** (`box-shadow: 0 1px 2px rgb(15 20 23 / 0.05), 0 6px 20px rgb(15 20 23 / 0.06)`; `none` in dark): every raised panel.
- **Lift** (`box-shadow: 0 2px 6px rgb(15 20 23 / 0.08), 0 14px 32px rgb(15 20 23 / 0.1)`; dark `0 12px 32px rgb(0 0 0 / 0.45)`): hovered quote card, chart tooltip, sign-in form, toast, phone lock bar.
- **Mood halo** (`box-shadow: 0 0 0 4px var(--mood-soft)`): hover on the primary button and Lock card (3px on the soft button).
- **Segment thumb** (`box-shadow: 0 1px 3px rgb(0 0 0 / 0.12)`): the pressed option in a segmented control.

### Named Rules
**The Lift-on-Intent Rule.** Panels rest on the soft shadow; only something the user is pointing at or must act on now gets the lift. Hovered quote cards rise 2px.

**The Dark-Is-Flat Rule.** In dark, resting panels carry no shadow; separation comes from the ground, card and sunk values.

## Shapes

Generously rounded, never sharp. Panels are 14px; inset wells and notices are 10px; quote chips, tooltips and the mobile tab target are 12px; the sign-in sheet is 20px and the lock bar 18px. Every interactive control (buttons, league pills, inputs, segmented controls, status items, badges, the count) is a full pill. Dots are circles. Borders are always 1px hairlines in line or line-2; a dashed silver border marks things that are testing or empty. The brand mark is a 9px-radius rounded square in the mood colour with a rising line and a dot.

## Components

### Buttons
- **Shape:** full pill (999px), 36px minimum height, 13px bold label, 7px 16px padding; 15px icons.
- **Primary:** mood fill with on-mood text. Larger in context: Add all is 46px tall at 15px, the card-footer primary 42px, the Lock card pill 48px at weight 800.
- **Soft:** mood tint with mood-ink text; the per-card "Add to tonight's card" action.
- **Secondary:** card ground, line-2 border; hover sinks to the sunk value.
- **Link:** underlined ink-2 text, no frame ("Show the math", Clear).
- **Danger:** coral outline that fills with coral tint on hover.
- **Hover / Active:** primary and soft gain the mood halo; all buttons press to scale(0.97) over 160ms on the house ease. Disabled buttons sink to the sunk value with muted text.

### Chips
- **Status pills:** 12px bold on a tint: ok (green), no (coral), warn (amber), neutral (sunk). A testing rule is a transparent pill with a dashed silver border.
- **League pills:** 32px card pills with a coloured dot; the selected league gets an ink border; unreleased leagues are transparent with a "soon" note.
- **Status strip items:** 13px card pills with a status dot; the running dot gets a 3px up-soft halo, a failing item turns coral on its tint.
- **Value meter:** four 14 x 6px rounded segments for 2/4/6/10 percent value, lit in good or bad.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** card, with a 1px line border.
- **Shadow Strategy:** Rest shadow; quote cards lift on hover (see Elevation).
- **Internal Padding:** 18px sides; header strips 12-16px top.

### Inputs / Fields
- **Style:** pill selects and search on the card ground with a line-2 border, 36px tall, 13px semibold; search carries an inset 15px icon. Sign-in inputs are 12px-radius, 48px tall at 16px on the ground value.
- **Focus:** a 2.5px focus-blue outline with 2px offset across every focusable element.

### Navigation
- **Desktop:** 15px bold tabs in ink-2; the current tab turns ink with a 3px mood underline rounded at the top. A mood count badge rides beside the Tonight tab.
- **Phones:** a fixed, blurred bottom bar of five equal 48px targets at 12px bold; the current item sits on the mood tint with mood-ink text.
- **Segmented control:** a sunk pill track with card-coloured pressed thumbs; a small variant at 28px.

### Quote Card (signature)
The unit of the desk. A header with a league dot, the matchup and tip time in 12px mute; the player name as a Title; the pick ("OVER 12.5 rebounds") with the side in bold ink. Then the quote row: three 12px-radius chips in a 1.25 : 1 : 1 grid. The first, "Hard Rock pays", sits on the mood tint with the price in mood-ink at Quote size; "Worth" and "Bet" sit on sunk at 17px. Beneath: the value meter with the edge in mood-ink at width 112, one plain-language line of why, any injury (amber tint) or line-move note (sunk), and a footer with the soft Add button and the "Show the math" link that opens a sunk drawer.

### Tonight's Card and Ticket
A docked panel: head with the title and meta, a list of legs (name, market, price at width 112, remove button that turns coral), the risk figure at Headline size over an 8px pill capacity bar in the mood colour (coral when over cap), a checks list with green ticks and coral crosses, and the full-width Lock card pill. Suggested legs sit under it on a sunk ground. Once locked, the head takes the mood tint and legs settle in with a staggered 320ms clip reveal (50ms per leg).

### Live pieces
Score chips are 14px-radius card tiles, 132px minimum, with team and score at 15px 800 wide; a live game gets a pulsing 7px dot. Bet progress reads in words at 13px, good or bad coloured.

### Strategy Chart
A card panel with a small segmented control to switch measure; one measure at a time, no second axis. Lines 2px with round joins and 3.5px points (5px on hover) ringed in the card colour; the control strategy is a dashed mute line. Grid in line, zero line in line-2, 11px mute labels, and a lifted 12px-radius tooltip.

### Toast
An inverted ink panel (14px radius), bottom right, with a mood dot (coral dot for errors), rising in over 260ms.

## Do's and Don'ts

### Do:
- **Do** route every primary action, active state and headline figure through the mood accent, and let `data-mood` decide green or coral.
- **Do** set player names and figures in Archivo at width 112, weight 800, with tabular numerals.
- **Do** put accent and status text on its own soft tint (up-soft, down-soft, warn-soft).
- **Do** keep panels at 14px radius with a 1px line border and the Rest shadow in light, no resting shadow in dark.
- **Do** make every interactive control a full pill at least 36px tall (44-48px for phone targets).
- **Do** keep 11px as the type floor and the 2.5px focus-blue outline on everything focusable.
- **Do** show league identity only as a 7-8px dot.

### Don't:
- **Don't** introduce a second accent colour or a second typeface.
- **Don't** colour surfaces, borders or type by league.
- **Don't** add resting shadows in dark, or hard offset shadows anywhere.
- **Don't** go back to the ink-ruled spreadsheet: no heavy black rules, no square-cornered panels.
- **Don't** add celebration or pressure: no confetti, streak flames, countdowns or bouncing motion; state changes stay at 120-320ms on the house ease and stop under reduced motion.
