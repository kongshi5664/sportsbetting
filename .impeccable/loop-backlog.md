# Site improvement loop: backlog

One item per round, highest value first. Each round: build, run tests, screenshot desktop 1440 and phone 390 (both themes when styling changes), commit to `live-desk` and push, then tick the item off here with the commit hash.

## Up next
- [ ] Capture the live score chips and bet progress once tonight's games tip (CLE @ PHI 7:10p ET). Fix anything that looks wrong in a live state.
- [x] Live progress on a locked real card (0c7376d)
- [ ] League dot from data, not hardcoded `--nba`: game rows, quote-card headers and team headings should read the league id (in Meta) and use `var(--<league>)`.
- [ ] Replace the text glyphs "✓ Hit" / "✗ Missed" in Live.tsx `Progress` with the drawn Check / Cross icons.
- [ ] Separate "live game" from "below the close": live dot and in-progress score border use their own token (not the coral mood colour).
- [ ] Clean Games System leftovers: unused `Pictogram`, the pictogram comment in icons.tsx, alias tokens `--rule`, `--rule-soft`, `--zone` and `--on-zone` (migrate usages), and UI icon caps to round so they match the mark.
- [ ] Collapse the duplicated dark-theme token blocks and the duplicate `.board .ref` rules in styles.css; fold the "fixes" blocks at the tail into their sections.
- [ ] Dark-theme `<option>` colours in the slate date selector.
- [ ] Beat-the-market chip: when there's data, show a tiny 14-day trend next to the figure.
- [ ] Motion: tick a quote when a price changes on refresh (brief highlight on the Hard Rock price), respecting reduced motion.
- [ ] Empty strategy chart: show a faint example of what will appear, labelled as an example.

## Done
