---
name: Tip-Off Desk
description: A private betting desk in the Games System, with one pictogram and one color zone per league on a strict ink grid.
colors:
  ground: "#ffffff"
  sunk: "#f4f5f5"
  ink: "#1b1d22"
  ink-2: "#474b54"
  mute: "#5f636c"
  rule: "#1b1d22"
  rule-soft: "#e3e4e5"
  silver: "#c7c9c8"
  on-zone: "#1b1d22"
  press-ink: "#33363d"
  league-nba: "#f28c28"
  league-nfl: "#3a9a4a"
  league-mlb: "#4fa3d8"
  league-nhl: "#c7c9c8"
  pass: "#0b6e5f"
  blocked: "#c41f3b"
  blocked-soft: "#fbe4e8"
  warning: "#7a5c00"
  warning-soft: "#f8efd3"
  focus: "#1f5fd6"
  ground-dark: "#121316"
  sunk-dark: "#1a1c20"
  ink-dark: "#eceef1"
  ink-2-dark: "#c3c7ce"
  mute-dark: "#9ba0a9"
  rule-dark: "#d9dce1"
  rule-soft-dark: "#2b2e34"
  silver-dark: "#4a4e56"
  pass-dark: "#45c9a9"
  blocked-dark: "#ff7088"
  blocked-soft-dark: "#3b1820"
  warning-dark: "#e7b84a"
  warning-soft-dark: "#352a10"
  focus-dark: "#7fa8ff"
typography:
  display:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "56px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.3
  brand:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.16em"
  figure:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 800
    lineHeight: 1.2
    fontFeature: "tnum"
  body:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tnum"
  control:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.4
  label:
    fontFamily: "Hanken Grotesk, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "0.08em"
rounded:
  none: "0px"
spacing:
  hair: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  gutter: "28px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
    typography: "{typography.control}"
    height: "34px"
  button-primary-hover:
    backgroundColor: "{colors.press-ink}"
  button-primary-dark:
    backgroundColor: "{colors.ink-dark}"
    textColor: "{colors.ground-dark}"
  button-secondary:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
    typography: "{typography.control}"
    height: "34px"
  button-secondary-hover:
    backgroundColor: "{colors.sunk}"
  button-disabled:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.mute}"
  button-lock:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "14px"
    height: "52px"
  button-lock-disabled:
    backgroundColor: "{colors.rule-soft}"
    textColor: "{colors.ink-2}"
  segmented-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
    height: "31px"
  pill-pass:
    textColor: "{colors.pass}"
    rounded: "{rounded.none}"
    padding: "1px 7px"
  pill-blocked:
    textColor: "{colors.blocked}"
    rounded: "{rounded.none}"
    padding: "1px 7px"
  pill-testing:
    textColor: "{colors.mute}"
    rounded: "{rounded.none}"
    padding: "1px 7px"
  tag-sample:
    backgroundColor: "{colors.silver}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "2px 7px"
  header-zone:
    backgroundColor: "{colors.league-nba}"
    textColor: "{colors.on-zone}"
    height: "64px"
  tab-active:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    padding: "0 18px"
    height: "44px"
  game-band:
    backgroundColor: "{colors.league-nba}"
    textColor: "{colors.on-zone}"
    height: "32px"
  card-head:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.title}"
    padding: "12px 16px"
  ticket-head:
    backgroundColor: "{colors.league-nba}"
    textColor: "{colors.on-zone}"
    padding: "12px 16px"
  league-tile:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    height: "92px"
    width: "88px"
  league-tile-active:
    backgroundColor: "{colors.league-nba}"
    textColor: "{colors.on-zone}"
  notice:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.ink}"
    padding: "10px 14px"
  toast:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    padding: "12px 16px"
---

# Design System: Tip-Off Desk

## Overview

**Creative North Star: "The Games System"**

Tip-Off Desk is one identity built to hold every sport, in the tradition of the Munich 1972 Games: each league owns a geometric pictogram and a flat color zone, and everything else is ink on white on a strict grid. The active league's color runs from the left rail tile, through the header band, into the game bands of the board, so the room is always painted in the color of the sport in play. Nothing else in the interface is decorative; the zone is the only spectacle.

The desk is dense and precise: a priced table is the primary surface, structure comes from 1.5 to 2px ink rules rather than boxes or shadows, every corner is square, and every number sits in tabular figures from a single typeface, Hanken Grotesk. It refuses the category default of a dark odds terminal with glowing green and red numbers. State (pass, blocked, warning) has its own teal, red and ochre, never borrows a league color, and always carries a mark or a word.

Dark is a designed night theme, not an inversion: a near-black ground, light ink rules, and brightened state colors, while the league zone keeps its exact hue so the identity reads the same at midnight.

**Key Characteristics:**
- White ground, ink #1b1d22, one flat league zone per sport (NBA orange live; NFL, MLB, NHL waiting).
- Hanken Grotesk only, weights 400/600/700/800, tabular figures everywhere.
- Ink rules (1.5px controls, 2px structure, 1px soft row dividers), square corners, no shadows, no gradients.
- Geometric pictograms and icons on a 45/90 grid with square caps and miter joins.
- State colors are reserved, always paired with a mark or word.
- Motion is small and functional: a ticket settling, a toast rising, a bar filling.

## Colors

A white-and-ink system with one committed league zone per sport and a separate, reserved state triad.

### Primary
- **League Zone, NBA Court Orange** (league-nba): the live league's zone. Fills the active rail tile, the full header band, the game-group bands on the board, the Player-out team bars, the locked ticket head, the actual-CLV line on the ledger chart, the tab-bar active stripe, text selection and the caret. Text on it is always ink (on-zone), never white. It is the same in both themes.

### Secondary
- **League Zones, waiting** (league-nfl Field Green, league-mlb Diamond Blue, league-nhl Rink Silver): reserved for their leagues. Shown at 22% mixed into the ground on inactive rail tiles; they become the full zone when that league goes live. They also make up the four-square brand mark.

### Tertiary (state)
- **Pass Teal** (pass / pass-dark): passing rules, positive edge and CLV, the edge ramp, wins.
- **Blocked Red** (blocked / blocked-dark, blocked-soft): failing rules, negative values, a failing leg's row tint, an over-cap capacity bar, remove-leg hover, error toasts.
- **Warning Ochre** (warning / warning-dark, warning-soft): sample-data and caveat notices, ruled into a soft ochre box.
- **Focus Blue** (focus / focus-dark): the 2.5px keyboard focus outline only.

### Neutral
- **Ground** (ground / ground-dark): page and control backgrounds.
- **Sunk** (sunk / sunk-dark): row hover, expanded proof rows, on-card rows, secondary-button hover.
- **Ink** (ink / ink-dark): text, primary buttons, card head, toast, capacity fill. Also the rule color in light mode.
- **Ink 2** (ink-2 / ink-2-dark): secondary text, column heads, captions, held-out rows.
- **Mute** (mute / mute-dark): reference-book prices, meta text, testing pills, disabled text.
- **Rule** (rule / rule-dark): structural ink rules. In dark it is a light rule (#d9dce1), not the ink color.
- **Rule Soft** (rule-soft / rule-soft-dark): 1px row dividers, empty ramp cells, chart gridlines, disabled lock.
- **Silver** (silver / silver-dark): the Sample tag, dashed empty-state borders, scrollbar thumb.
- **Press Ink** (press-ink): hover state of solid ink buttons in light mode.

### Named Rules
**The Zone Belongs To The League Rule.** The league color marks the sport in play and nothing else. It never signals good, bad, primary action or emphasis. A second league goes live by switching the zone variable, not by adding new accents.

**The State Never Borrows Rule.** Pass, blocked and warning use their own teal, red and ochre and always ship with a check, cross, warning mark or a word. Color alone never carries state.

**The Ink On Zone Rule.** Text on any league zone is ink (#1b1d22), in both themes.

## Typography

**Display Font:** Hanken Grotesk (with system-ui, sans-serif)
**Body Font:** Hanken Grotesk
**Label/Mono Font:** none; figures are Hanken Grotesk with tabular-nums

**Character:** One grotesque carries everything, from the 56px CLV figure to the 11px column head. Hierarchy comes from weight (400 body, 600 secondary, 700 controls and names, 800 figures and headings) and size, not from a second family.

### Hierarchy
- **Display** (800, 56px, line-height 1, -0.02em; 44px under 860px): the lead CLV figure on the Ledger. One per view.
- **Headline** (800, 28px, -0.01em; 24px under 860px): the view title line (Edge Board, Ledger & CLV, Rulebook, Player out), followed inline by a plain counts sentence.
- **Title** (800, 18px): section heads, rule groups, the card head, empty-state heads. Larger figures in the same weight: 32px risk total, 28px ledger secondary figure, 22px Player-out head, 21px header stats.
- **Brand** (800, 21px, 0.16em, uppercase; 17px on phone): the TIP-OFF DESK wordmark only.
- **Figure** (800, 17px): the Hard Rock price in the board, and leg prices on the card (16px).
- **Body** (400, 14px, line-height 1.4): everything else. Prose caps at 65 to 72ch.
- **Control** (700, 13px; tabs 15px): buttons, segmented filters, fields.
- **Label** (800, 11px, 0.08 to 0.1em, uppercase): table column heads, header stat names, proof-panel subheads, results. 11px is the floor; nothing smaller.

### Named Rules
**The One Family Rule.** Hanken Grotesk is the only typeface. No monospace for numbers, no condensed display face.

**The Tabular Figures Rule.** Body sets `tabular-nums`; every price, stake, edge and CLV column aligns.

**The True Minus Rule.** Numbers are formatted once, in one way: American odds with a true minus sign (+181, −110), signed percents to one decimal (+7.5%, −1.9%), units with a "u" (+1.4u), money without cents unless settling ($124, +$12.40), tip times in Eastern as 7:30p, and an em dash for a missing value.

## Layout

A three-part desk on a strict grid: an 88px pictogram rail on the left, running full height and sticky; a 64px sticky league-zone header across the top (brand and slate, tabs, then stats right-aligned and divided by 2px rules); and a main area with 28px left gutter (24px top, 40px bottom). On the Edge Board the main area splits into the board and a 340px docked Card with a 24px gap; the Card is sticky 88px from the top.

The board is a full-width collapsed table: 42px rows divided by 1px soft rules, a 2px ink rule under the column heads, 32px zone bands as game-group headers, and the Hard Rock column boxed between two 2px ink rules. Reference-book prices sit to its right in muted 13px. A filter row sits between a 2px rule above and a 1px soft rule below. The Ledger leads with a ruled strip of figures (2px rule above, 1px below, 1px soft dividers between). The Rulebook is a three-column row per rule (rule, evidence, actions). Spacing works in 2/4/8/12/16/24/28/32px steps, with 6, 10 and 14px used inside dense controls.

**Breakpoints.**
- **At 1180px and below:** the docked Card leaves the Edge Board (it remains its own tab), reference-book columns hide, only the last header stat (Avg CLV) stays, and tab padding tightens to 12px.
- **At 860px and below:** the rail and header tabs hide; the header shrinks to 56px with 16px padding and safe-area inset; a fixed bottom tab bar of five 56px targets appears, with a 4px zone stripe on the active tab and an ink count badge. Main padding becomes 16px with 96px bottom clearance. Board rows stack into a grid: player and Hard Rock price (fair beneath) on top, market and edge below, a 44px Add button spanning both, and rule pills on a third line. The Ledger strip goes two-up, split views go single column, rule rows stack, and the toast spans the width above the tab bar.

**The Rail-To-Band Rule.** The active league's color always runs continuously from the rail tile through the header into the game bands. Any new surface that groups by game or team uses a zone band, not a card.

## Elevation & Depth

Flat by construction. There are no drop shadows and no gradients anywhere. Depth is conveyed by ink rules (2px for structure, 1.5px for controls, 1px soft for rows), by solid ink or zone fills for the few elements that must stand out (header, card head, primary and lock buttons, toast), and by the sunk tone for hover and expanded rows. Stickiness (rail, header, docked card) provides layering without shadow.

**The Rule Not Shadow Rule.** If something needs to separate, draw an ink rule or fill it solid. A shadow is never the answer.

## Shapes

Every corner is square (0px). Boxes are made of rules: 1.5px ink for buttons, fields, segmented controls and pills; 2px ink for the card, the rail edge, the footer and section tops. Dashed borders mean "not enforced" or "nothing here": testing pills are dashed, empty states are a 1.5px dashed silver box. The pictograms and icon family share one geometry: a 24px (icons) or 32px (pictograms) grid, strokes on 45/90 degree angles, square caps and miter joins, solid circles for heads and balls. The brand mark is four 11px squares in the four league colors.

## Components

### Buttons
Solid, square and blunt; ink does the work.
- **Shape:** square corners, 1.5px ink border, 34px minimum height, 13px/700 label, 6px gap for an optional 14px icon.
- **Primary:** solid ink with white text; in dark it inverts to light ink on the dark ground. Hover goes to Press Ink in light mode.
- **Secondary:** ground with ink border; hover fills Sunk.
- **Link:** no border, underlined, ink-2, 600; hover to ink.
- **Danger:** ink border swapped for Blocked Red border and text.
- **Disabled:** silver border, mute text, ground fill, not-allowed cursor; the reason is always stated nearby.
- **Lock card:** the one large action. Full-width ink slab, 52px tall, 15px/800 with 0.04em tracking, lock icon and the total ("Lock card · $124"). Disabled it drops to Rule Soft with ink-2 text. Clear sits set apart to its right as an underlined link behind a 1px soft rule, turning red on hover.
- **Add:** 76px secondary button per board row; when the leg is on the card it fills solid ink and reads "On card" with a check. 44px tall on phone, with the stake shown.

### Chips (pills)
- **Style:** 1.5px border in the text color, transparent fill, 12px/700, square, a 12px icon before the word.
- **Variants:** Pass (teal, check), blocked rule (red, cross, names the rule), testing (mute, dashed border, 600, "1 testing"), warning (ochre).
- **Tag:** the Sample label is a solid silver block with 11px/800 uppercase ink text, in the header and the footer.

### Cards / Containers
- **Tonight's Card:** 2px ink frame, ground fill, square. Head is a solid ink bar (title 18px/800, meta in #c9ccd2). Legs are a three-column grid (what, price, remove) with 1px soft dividers; a failing leg tints Blocked Soft and names the failing rule beneath in red. Then the risk block (32px figure "of $160 cap", a 12px capacity bar filling in ink, red when over), the named checks list (check or cross per rule), and the Lock slab.
- **Ticket (locked):** the same card settles into a ticket. The head turns to the league zone, each leg gets a placed checkbox, placed legs strike through, and legs animate in.
- **Notice:** 1.5px Warning Ochre border on Warning Soft, warning icon, 72ch max.
- **Empty state:** 1.5px dashed silver box, 28px padding, 18px/800 head and an ink-2 line.

### Inputs / Fields
- **Style:** 1.5px ink border, ground fill, square, 34px tall, 13px/600. Search carries a 15px muted search icon inset 9px. Checkboxes are 16px with ink accent color.
- **Focus:** a 2.5px Focus Blue outline offset 2px on every focusable element (inset 2.5px on board rows).

### Navigation
- **Rail:** 88px wide; ink brand-mark block (64px) on top, then one 92px tile per league: 38px pictogram and an 11px/800 tracked label. Active tile is the full zone; waiting leagues show at 22% zone mix with a "soon" line and are disabled. The theme toggle (sun or moon) sits at the foot.
- **Header tabs:** 44px tall, 15px/700, ink on zone; hover lifts with a 22% ground wash; the active tab becomes a ground-colored tab cut into the band. The Card tab carries an ink count badge. Keys 1 to 5 switch tabs.
- **Header stats:** 11px uppercase label over a 21px/800 figure, divided by 2px rules at 45% ink.
- **Phone tab bar:** see Layout; the active tab gets a 4px zone stripe on its top edge.

### Edge Board (signature)
The board is the system in one component: zone bands per game, the Hard Rock price boxed in ink rules at 17px/800, fair price beside it, reference books muted, edge in teal with a four-cell ramp (cells light at 2, 4, 6 and 10% edge), stake, rule pills, Add. Sortable heads show a 10px chevron and darken to ink when sorted. Clicking a row expands a sunk proof panel: the de-vigged reference table and the pricing math in plain words.

### Toast
Solid ink bar, white 600 text, 420px max, bottom-right, with a 10px square in the zone color (red for errors) leading it. Rises 8px over 220ms.

### Motion
One easing, `cubic-bezier(0.16, 1, 0.3, 1)`. The capacity bar fills over 240ms; ticket legs settle in over 280ms with a 45ms stagger (a right-to-left clip and 4px rise); the toast rises over 220ms. View changes do not animate. `prefers-reduced-motion` removes all animation and transition.

## Do's and Don'ts

### Do:
- **Do** paint the live league's zone from rail to header to game bands, with ink text on it.
- **Do** set every number in Hanken Grotesk tabular figures, with the true minus sign and one formatting convention (format.ts).
- **Do** show the fair price beside every Hard Rock price, and box the Hard Rock column in 2px ink rules.
- **Do** pair every state color with a check, cross, warning mark or word, and name the rule that blocks.
- **Do** separate with ink rules: 2px for structure, 1.5px for controls, 1px Rule Soft for rows.
- **Do** keep targets at 44px or more on phone, and the 2.5px Focus Blue outline on everything focusable.
- **Do** label sample data with the silver Sample tag and keep 1-800-GAMBLER in the footer.
- **Do** write short, plain, specific copy in a bettor's words ("104 clear the rulebook", "Locking freezes these prices"), sentence case except the brand and 11px labels.
- **Do** draw new icons on the 24px grid with 2.4 strokes, square caps, miter joins and 45/90 angles; new league pictograms on the 32px grid at 3.4 strokes.

### Don't:
- **Don't** use a league color to mean good, bad, primary or emphasis, and don't introduce any accent outside the league zones and the state triad.
- **Don't** round corners, add shadows or use gradients.
- **Don't** add a second typeface, a monospace for numbers, or a condensed display face.
- **Don't** build a dark odds terminal with glowing green and red numbers, or any casino styling: confetti, streak flames, countdowns, hype words like "lock of the day".
- **Don't** put sport-specific detail (team colors, sport names, stat vocabulary) into the shell, palette or type; it comes from data.
- **Don't** set text smaller than 11px, or rely on color alone for state.
- **Don't** add small uppercase labels above headings as decoration; uppercase 11px is for column heads, stat names and data labels only.
- **Don't** animate view changes or celebrate wins.
