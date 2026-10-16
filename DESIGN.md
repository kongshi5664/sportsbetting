# DESIGN.md — Tip-Off Desk

Source of truth: `web/index.html` (the prototype). Keep new screens consistent with it.

## Direction

A sportsbook terminal crossed with an arena scoreboard: a dense, precise working tool with one loud color. It's an instrument for reading prices, not a marketing page. Personality comes from type and the accent, not from decoration.

## Color tokens

Light theme first; dark theme is a full, designed palette, not an inversion. Never use a color outside these tokens.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f3f5f9` | `#0c1222` | Page ground (cool paper / deep navy) |
| `--panel` | `#ffffff` | `#141c30` | Tables, cards, inputs |
| `--ink` | `#131c33` | `#e8ecf6` | Primary text |
| `--muted` | `#5b6680` | `#97a2bd` | Labels, secondary text, chart text |
| `--line` | `#dde2ec` | `#26304a` | Borders, table rules, gridlines |
| `--accent` | `#e2550f` | `#ff7a33` | Court orange: primary action, active tab, actual-results line |
| `--accent-soft` | `#fde8dc` | `#3a2214` | Accent tint behind pills |
| `--good` / `--good-soft` | `#10875a` / `#dcf3e8` | `#3ccf8e` / `#123326` | Positive EV/CLV, best price, passing check, wins |
| `--bad` / `--bad-soft` | `#c2333a` / `#fbe3e4` | `#ff6b72` / `#3a171b` | Negative EV/CLV, failed rule, losses |
| `--warn` / `--warn-soft` | `#a96a00` / `#fbf0d6` | `#f2b84b` / `#352a12` | Testing rules, Hard Rock caveats |
| `--head` / `--head-fg` | `#131c33` / `#eef1f8` | `#070b16` / `#eef1f8` | Sticky scoreboard header (dark in both themes) |

Semantic colors (good/bad/warn) are not the accent. Orange never means "good."

## Type

- **Display:** Barlow Condensed 600–700, uppercase, slight tracking. Brand, tab labels, section headings, big KPI numbers. Scoreboard voice; use sparingly.
- **Body:** IBM Plex Sans 400–600, 14px base, ~65–72ch line length for prose.
- **Numbers:** JetBrains Mono for every odds price, stake, edge, CLV and score, with `tabular-nums`. Odds always render as American with a true minus sign (−110, +145).
- Uppercase micro-labels: 10.5–11px, letter-spacing .08–.12em, `--muted`.

## Layout

- Max width 1180px, 16px minimum side gutter (safe-area aware).
- Sticky dark header: brand, live bankroll/unit/CLV/units stats, then tabs (Edge Board, Tonight's Card, Rulebook, Ledger & CLV, Game Plan).
- Tables are the primary surface. Wide tables scroll inside their own container; the page never scrolls sideways.
- Two-column work areas (slip + checks) collapse to one column under 860px.
- Panels: 1px `--line` border, 6px radius, no shadows.

## Components

- **Price cell:** mono; best available price gets a `--good-soft` chip. Fair price in `--muted` beside it.
- **Pills:** small rounded labels for state: Pass, Below 2% edge, Player cap, Confirmed, Testing, Retired, Win, Loss. State is always shown as a pill, never by color alone.
- **Checks list:** ✓ / ✕ / ! in mono, colored by state, followed by the rule in plain words.
- **Buttons:** Barlow Condensed uppercase. Primary = solid accent. Disabled = 45% opacity with the reason shown nearby.
- **Charts:** hand-drawn SVG, one scale, faint gridlines, area fill under the actual line, dashed `--good` line for CLV-expected, emphasized endpoint dot. Chart text uses `--muted`.

## Voice

Short, plain, specific. Name things the way a bettor would. Say why a bet is blocked. No hype words ("lock," "hammer," "guaranteed"), no emoji.

## Motion

Minimal: a 180ms fade/rise when switching tabs, a toast on lock. Respect `prefers-reduced-motion`. No celebratory animation on wins.

## Avoid

Casino styling, neon gradients, glassmorphism, confetti, card grids of identical rounded boxes, emoji section markers, purple-to-blue heroes, and generic Inter/Space Grotesk defaults.
