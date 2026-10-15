# Layout tokens: per-layout values, league-driven roles, deviations

Notes written by the agents that produced `assets/css/layouts/*.css` (Basketball, Classic, Scoreboard first; Curling,
Hockey, Slo-pitch second). The CSS is the source of truth; this explains the choices. Two corrections after the notes
were written: (1) team palettes follow the order in `docs/dark-palettes.md` (not standings order) in every layout, to
match the sample data's `slot`; (2) several `header-button-line`, hockey dark `hot`, `won-line` and `line-strong`/`mark-line`
contrast fixes came from `scripts/check_contrast.py` (see `docs/contrast.md`).

# Layouts A: basketball, classic, scoreboard

Files written (only these): `assets/css/layouts/basketball.css`, `classic.css`, `scoreboard.css`.
Values below are the RESOLVED colours (league helpers evaluated with the default league colour, oklab,
same maths as `color-mix(in oklab, ...)`). The throwaway tools are in `scratchpad/tools/`
(`layouts.py` holds the role values, `emit.py` writes the CSS, `check.py` the contrast pairs); the CSS files were
generated from them, so the two dark blocks are identical by construction (also verified by re-parsing).

## Structure checks run
- braces and parentheses balanced in all three files;
- the `@media` dark block and the `[data-theme="dark"]` block hold identical declarations (compared line by line);
- every role in the docs/design.md table is defined in each light block; every `var(--st-*)` used is defined in the
  file or in tokens.css; no file paths and no external URLs (scene SVGs are `data:` URIs, `#` encoded as `%23`,
  single quotes inside; they parse as XML).
- Dark blocks hold only values that differ from light (plus the dark team palette, `--st-team-lift: 20%`, and the scene images).
- `--st-league-color-dark` / `-2-dark` are deliberately NOT given defaults: an inline `--st-league-color` set by a league
  must recolour dark too (a layout default for the dark input would shadow nothing but would freeze the old dark colour).

## Decisions
- **Basketball** default league colour #032F98 (deep blue), second colour #FF5C66 (coral). Knob `--st-dim: 18%` (dark panel
  = league colour toward black); `--st-tint` stays 62% (fit 61%). Light header = the sunrise gradient with the league
  colour as its top 58%, then fixed sunrise stops; dark header = night sky mixed from the league colour and the ink #0A1022
  (stops fitted to the approved sky, dE 0-2). Hills, arcs, moon, stars are baked (neutral scene).
- **Classic** default league colour curling navy #1D3A6E, second colour #9E1B32 (burgundy: the stolen-end / hot red, lead bar).
  Knobs `--st-lift: 8%` (dark nav bar), `--st-tint: 65%` (dark text accent). Team palette is curling's.
- **Scoreboard** default league colour red #CB0E1D (the colour of the basketball mockup). The dark mockup was drawn with
  green (#2F6B3A lifted to #2B7539), so the knobs were fitted on that pair (`--st-lift: 4%`, `--st-tint: 55%`) and the
  red derives from them. Amber #FFC233 is NOT the league colour: it is a literal in every digit role (score-text, rank-1-text,
  mark-*, won-line, bar-lead, badge-text, tile text) and the default of `--st-layout-accent`, which drives only `tab`
  (tokens.css documents league-color-2 as "tab underline, rules"). A league that changes color-2 therefore changes only the tab underline.
- Scoreboard has no team chips in its mockups (tokens.css says chips are not shown); the palette is basketball's five
  (blue, teal, orange, green, purple) plus curling's grey as slot 6. Basketball slot 6 is magenta #B3306E / #F27AB0
  (distinct from blue, teal, orange, green, purple and from the coral tab).
- Scoreboard's mockup card outline is a 2 px ink line (`line-strong` + `border-strong`), while dividers are `line`
  (#DDDDDD): so `--st-line-strong` is #111111 / #E8E8E8 and `--st-border-strong: 2px` is set explicitly. base.css cards use
  `--st-line` at `--st-border`: the parts agent needs a Scoreboard rule for the 2 px ink outline.
- Fonts: Barlow pair (weights 700 display, 600 strong); Scoreboard Anton (only weight 400, so `--st-w-display: 400`) +
  Chakra Petch (`--st-font-num` is Chakra Petch for digits; Anton big numbers should use `--st-font-display`).
  `--st-fs-*` overrides: Scoreboard `fs-h2` = step-5xl (32 px) and `fs-score-hero` = step-6xl (40 px; the mockup digit
  boxes use 44 px, which is not on the scale). Basketball and Classic match the default bindings (the Classic curling stat
  tile is 34 px in the mockup, Classic hockey 40 px: default 40 kept).
- Scene rules (basketball): header scene = two background layers in one `--st-scene-image` (hills, repeat-x and seamless;
  court arcs, centred, no-repeat; dark adds moon and stars), 56 px, `margin-top: 6px`, at the end of the header, so the header
  background gradient shows through. Footer scene = hills, 40 px, with the page colour baked into the image so it works
  whichever element carries the footer background. Classic and Scoreboard: `display: none` for both scene boxes.


## Basketball

### Role values (resolved, default league colour)

| role | light | dark | league-driven |
|---|---|---|---|
| `bg` | #F4F6FB | #0A1022 |  |
| `bg-image` | none | none |  |
| `surface` | #FFFFFF | #131B34 |  |
| `surface-2` | #ECEFF8 | #1A2444 |  |
| `line` | #E3E8F2 | #243052 |  |
| `line-strong` | #C8D0E4 | #3A4A7A |  |
| `text` | #0B1B3F | #EEF2FF |  |
| `muted` | #5A6478 | #9AA6C4 |  |
| `link` | #032F98 | #9AB1DC | yes |
| `link-hover` | #0B1B3F | #EEF2FF |  |
| `accent` | #032F98 | #9AB1DC | yes |
| `hot` | #B74047 | #FF5C66 | yes |
| `rule` | #032F98 | #9AB1DC | yes |
| `focus` | #032F98 | #9AB1DC | yes |
| `button-bg` | #032F98 | #9AB1DC | yes |
| `on-accent` | #FFFFFF | #0A1022 |  |
| `header-bg` | gradient: #032F98@0% / #032F98@58% / #3A2A8C@74% / #B23A5E@88% / #EE6A2F@100% | gradient: #0A1022@0% / #0B193E@50% / #1E3C81@76% / #4263A7@100% | yes |
| `header-text` | #FFFFFF | #FFFFFF |  |
| `header-muted` | #D4DEF1 | #B8C3E0 | yes |
| `header-line` | transparent | transparent |  |
| `header-button-line` | #FFFFFF73 | #FFFFFF73 |  |
| `tab` | #FF5C66 | #FF5C66 | yes |
| `nav-bg` | transparent | transparent |  |
| `nav-text` | #FFFFFF | #FFFFFF |  |
| `nav-muted` | #D4DEF1 | #B8C3E0 | yes |
| `panel-bg` | #032F98 | #022274 | yes |
| `panel-text` | #FFFFFF | #FFFFFF |  |
| `panel-muted` | #C9D6ED | #BCCBE8 | yes |
| `panel-label` | #C9D6ED | #BCCBE8 | yes |
| `panel-row` | #FFFFFF1F | #FFFFFF14 |  |
| `panel-line` | #FFFFFF26 | #FFFFFF26 |  |
| `panel-tile-bg` | #E4EAF6 | #E4EAF6 | yes |
| `panel-tile-text` | #022274 | #022274 | yes |
| `footer-bg` | #0B1B3F | #18214D |  |
| `footer-text` | #C9D4F2 | #B8C3E0 |  |
| `footer-muted` | #A9B6DA | #A9B6DA |  |
| `footer-link` | #FFFFFF | #FFFFFF |  |
| `footer-line` | #FFFFFF26 | #FFFFFF26 |  |
| `footer-accent` | #FF5C66 | #FF5C66 | yes |
| `mark-bg` | #FFE8E7 | #2E0A0C | yes |
| `mark-text` | #631F23 | #FFC5C4 | yes |
| `mark-line` | #FFA3A2 | #9E363C | yes |
| `won-line` | #FF5C66 | #FF5C66 | yes |
| `blank-bg` | #ECEFF8 | #1A2444 |  |
| `badge-bg` | #E4EAF6 | #0E2769 | yes |
| `badge-text` | #032F98 | #9AB1DC | yes |
| `win-bg` | #DDF1E0 | #17361F |  |
| `win-text` | #17602A | #8FDC9A |  |
| `rank-bg` | transparent | transparent |  |
| `rank-text` | #5A6478 | #9AA6C4 |  |
| `rank-1-bg` | transparent | transparent |  |
| `rank-1-text` | #032F98 | #9AB1DC | yes |
| `bar-track` | #E3E8F2 | #243052 |  |
| `bar-fill` | #032F98 | #9AB1DC | yes |
| `bar-lead` | #B74047 | #FF5C66 |  |
| `score-bg` | #032F98 | #022274 | yes |
| `score-text` | #FFFFFF | #FFFFFF |  |
| `score-dim` | #C9D6ED | #BCCBE8 | yes |
| `score-line` | #FFFFFF40 | #FFFFFF40 |  |

League-driven roles (written with league helpers): `link`, `accent`, `hot`, `rule`, `focus`, `button-bg`, `header-bg`, `header-muted`, `tab`, `nav-muted`, `panel-bg`, `panel-muted`, `panel-label`, `panel-tile-bg`, `panel-tile-text`, `footer-accent`, `mark-bg`, `mark-text`, `mark-line`, `won-line`, `badge-bg`, `badge-text`, `rank-1-text`, `bar-fill`, `score-bg`, `score-dim`

### Contrast (WCAG ratios, lowest per pair; header pairs use the stops the text sits on)

| pair | light | dark | need |
|---|---|---|---|
| text/bg | 15.63 | 16.92 | 4.5 |
| text/surface | 16.90 | 15.22 | 4.5 |
| text/surface-2 | 14.70 | 13.61 | 4.5 |
| muted/bg | 5.50 | 7.77 | 4.5 |
| muted/surface | 5.95 | 6.99 | 4.5 |
| muted/surface-2 | 5.18 | 6.25 | 4.5 |
| link/bg | 10.42 | 8.73 | 4.5 |
| link/surface | 11.27 | 7.86 | 4.5 |
| link/surface-2 | 9.80 | 7.03 | 4.5 |
| link-hover/bg | 15.63 | 16.92 | 4.5 |
| link-hover/surface | 16.90 | 15.22 | 4.5 |
| link-hover/surface-2 | 14.70 | 13.61 | 4.5 |
| accent/bg | 10.42 | 8.73 | 4.5 |
| accent/surface | 11.27 | 7.86 | 4.5 |
| accent/surface-2 | 9.80 | 7.03 | 4.5 |
| hot/bg | 5.06 | 6.28 | 4.5 |
| hot/surface | 5.47 | 5.65 | 4.5 |
| hot/surface-2 | 4.76 | 5.06 | 4.5 |
| rule/surface | 11.27 | 7.86 | 3 |
| focus/bg | 10.42 | 8.73 | 3 |
| focus/surface | 11.27 | 7.86 | 3 |
| header-text/header | 11.11 | 10.40 | 4.5 |
| header-muted/header | 8.21 | 5.91 | 4.5 |
| tab/header | 3.69 | 3.46 | 3 |
| header-button-line/header | 3.42 | 4.53 | 3 |
| nav-text/nav | 11.11 | 10.40 | 4.5 |
| nav-muted/nav | 8.21 | 5.91 | 4.5 |
| tab/nav | 3.69 | 3.46 | 3 |
| panel-text/panel-bg | 11.27 | 14.15 | 4.5 |
| panel-text/panel-row | 8.27 | 11.58 | 4.5 |
| panel-muted/panel-bg | 7.69 | 8.66 | 4.5 |
| panel-muted/panel-row | 5.64 | 7.08 | 4.5 |
| panel-label/panel-bg | 7.69 | 8.66 | 4.5 |
| panel-label/panel-row | 5.64 | 7.08 | 4.5 |
| panel-tile-text/tile-bg | 11.73 | 11.73 | 4.5 |
| footer-text/footer-bg | 11.41 | 8.74 | 4.5 |
| footer-muted/footer-bg | 8.36 | 7.62 | 4.5 |
| footer-link/footer-bg | 16.90 | 15.40 | 4.5 |
| footer-accent/footer-bg | 5.61 | 5.12 | 3 |
| mark-text/mark-bg | 10.25 | 12.05 | 4.5 |
| mark-line/mark-bg | 1.63 | 2.62 | 1.0 |
| badge-text/badge-bg | 9.33 | 6.41 | 4.5 |
| win-text/win-bg | 6.46 | 8.13 | 4.5 |
| rank-text/rank-bg | 5.95 | 6.99 | 4.5 |
| rank-1-text/rank-1-bg | 11.27 | 7.86 | 4.5 |
| on-accent/button-bg | 11.27 | 8.73 | 4.5 |
| button-bg/bg (non-text) | 10.42 | 8.73 | 3 |
| score-text/score-bg | 11.27 | 14.15 | 4.5 |
| score-dim/score-bg | 7.69 | 8.66 | 4.5 |
| won-line/score-bg (non-text) | 3.74 | 4.70 | 3 |
| bar-fill/bar-track | 9.17 | 5.99 | 3 |
| bar-lead/lead-track | 4.45 | 4.31 | 3 |
| team-1/surface | 5.25 | 6.10 | 3 |
| team-2/surface | 4.77 | 8.28 | 3 |
| team-3/surface | 3.68 | 8.10 | 3 |
| team-4/surface | 5.13 | 7.91 | 3 |
| team-5/surface | 7.38 | 6.37 | 3 |
| team-6/surface | 5.89 | 6.63 | 3 |

### Achieved vs approved

| role | approved | achieved | dE |
|---|---|---|---|
| link | #8FB0FF | #9AB1DC | 5.3 |
| panel-bg | #1A2B6B | #022274 | 3.8 |
| panel-muted | #B8CCFF | #BCCBE8 | 3.2 |
| tab | #FF5C66 | #FF5C66 | 0.0 |
| hot | #FF5C66 | #FF5C66 | 0.0 |
| header-bg (stop 0) | #0A1022 | #0A1022 | 0.0 |
| header-bg (stop 1) | #111A3E | #0B193E | 0.9 |
| header-bg (stop 2) | #2C3A80 | #1E3C81 | 1.6 |
| header-bg (stop 3) | #4F5EA8 | #4263A7 | 2.0 |

## Classic

### Role values (resolved, default league colour)

| role | light | dark | league-driven |
|---|---|---|---|
| `bg` | #F4F6FB | #0B1220 |  |
| `bg-image` | none | none |  |
| `surface` | #FFFFFF | #141D30 |  |
| `surface-2` | #EDF0F7 | #1B2740 |  |
| `line` | #E3E8F2 | #26324A |  |
| `line-strong` | #C8D0E4 | #3A4A6E |  |
| `text` | #0B1B3F | #EEF2FA |  |
| `muted` | #5A6478 | #A0AAC0 |  |
| `link` | #1D3A6E | #AAB6CC | yes |
| `link-hover` | #0B1B3F | #EEF2FA |  |
| `accent` | #1D3A6E | #AAB6CC | yes |
| `hot` | #9E1B32 | #DA9B9C | yes |
| `rule` | #1D3A6E | #AAB6CC | yes |
| `focus` | #1D3A6E | #AAB6CC | yes |
| `button-bg` | #1D3A6E | #AAB6CC | yes |
| `on-accent` | #FFFFFF | #0B1220 |  |
| `header-bg` | #FFFFFF | #141D30 |  |
| `header-text` | #1D3A6E | #AAB6CC | yes |
| `header-muted` | #5A6478 | #A0AAC0 |  |
| `header-line` | #E3E8F2 | #26324A |  |
| `header-button-line` | transparent | transparent |  |
| `tab` | #FFFFFF | #FFFFFF |  |
| `nav-bg` | #1D3A6E | #2D497A | yes |
| `nav-text` | #FFFFFF | #FFFFFF |  |
| `nav-muted` | #CED5E2 | #CED5E2 | yes |
| `panel-bg` | #1D3A6E | #1D3A6E | yes |
| `panel-text` | #FFFFFF | #FFFFFF |  |
| `panel-muted` | #CED5E2 | #CED5E2 | yes |
| `panel-label` | #CED5E2 | #CED5E2 | yes |
| `panel-row` | #FFFFFF1A | #FFFFFF1A |  |
| `panel-line` | #395482 | #395482 | yes |
| `panel-tile-bg` | transparent | transparent |  |
| `panel-tile-text` | #CED5E2 | #CED5E2 | yes |
| `footer-bg` | #0B1B3F | #060A14 |  |
| `footer-text` | #C9D4F2 | #C9D4F2 |  |
| `footer-muted` | #A9B6DA | #A9B6DA |  |
| `footer-link` | #FFFFFF | #FFFFFF |  |
| `footer-line` | #FFFFFF26 | #26324A |  |
| `footer-accent` | #AAB6CC | #AAB6CC | yes |
| `mark-bg` | #F7E5E4 | #510915 | yes |
| `mark-text` | #9E1B32 | #DA9B9C | yes |
| `mark-line` | #E2AEAF | #A93643 | yes |
| `won-line` | #FFFFFF | #FFFFFF |  |
| `blank-bg` | #EDF0F7 | #1B2740 |  |
| `badge-bg` | #E6EAF0 | #192D51 | yes |
| `badge-text` | #1D3A6E | #AAB6CC | yes |
| `win-bg` | #DDF1E0 | #17361F |  |
| `win-text` | #17602A | #8FDC9A |  |
| `rank-bg` | #E6EAF0 | #192D51 | yes |
| `rank-text` | #1D3A6E | #C9D1DF | yes |
| `rank-1-bg` | #1D3A6E | #AAB6CC | yes |
| `rank-1-text` | #FFFFFF | #0B1220 |  |
| `bar-track` | #E3E8F2 | #26324A |  |
| `bar-fill` | #1D3A6E | #AAB6CC | yes |
| `bar-lead` | #9E1B32 | #DA9B9C | yes |
| `score-bg` | #1D3A6E | #1D3A6E | yes |
| `score-text` | #FFFFFF | #FFFFFF |  |
| `score-dim` | #CED5E2 | #CED5E2 | yes |
| `score-line` | #FFFFFF40 | #FFFFFF40 |  |

League-driven roles (written with league helpers): `link`, `accent`, `hot`, `rule`, `focus`, `button-bg`, `header-text`, `nav-bg`, `nav-muted`, `panel-bg`, `panel-muted`, `panel-label`, `panel-line`, `panel-tile-text`, `footer-accent`, `mark-bg`, `mark-text`, `mark-line`, `badge-bg`, `badge-text`, `rank-bg`, `rank-text`, `rank-1-bg`, `bar-fill`, `bar-lead`, `score-bg`, `score-dim`

### Contrast (WCAG ratios, lowest per pair; header pairs use the stops the text sits on)

| pair | light | dark | need |
|---|---|---|---|
| text/bg | 15.63 | 16.69 | 4.5 |
| text/surface | 16.90 | 15.00 | 4.5 |
| text/surface-2 | 14.81 | 13.27 | 4.5 |
| muted/bg | 5.50 | 8.03 | 4.5 |
| muted/surface | 5.95 | 7.22 | 4.5 |
| muted/surface-2 | 5.22 | 6.38 | 4.5 |
| link/bg | 10.32 | 9.16 | 4.5 |
| link/surface | 11.15 | 8.23 | 4.5 |
| link/surface-2 | 9.78 | 7.28 | 4.5 |
| link-hover/bg | 15.63 | 16.69 | 4.5 |
| link-hover/surface | 16.90 | 15.00 | 4.5 |
| link-hover/surface-2 | 14.81 | 13.27 | 4.5 |
| accent/bg | 10.32 | 9.16 | 4.5 |
| accent/surface | 11.15 | 8.23 | 4.5 |
| accent/surface-2 | 9.78 | 7.28 | 4.5 |
| hot/bg | 7.31 | 8.16 | 4.5 |
| hot/surface | 7.90 | 7.33 | 4.5 |
| hot/surface-2 | 6.93 | 6.49 | 4.5 |
| rule/surface | 11.15 | 8.23 | 3 |
| focus/bg | 10.32 | 9.16 | 3 |
| focus/surface | 11.15 | 8.23 | 3 |
| header-text/header | 11.15 | 8.23 | 4.5 |
| header-muted/header | 5.95 | 7.22 | 4.5 |
| nav-text/nav | 11.15 | 8.95 | 4.5 |
| nav-muted/nav | 7.56 | 6.07 | 4.5 |
| tab/nav | 11.15 | 8.95 | 3 |
| panel-text/panel-bg | 11.15 | 11.15 | 4.5 |
| panel-text/panel-row | 8.29 | 8.29 | 4.5 |
| panel-muted/panel-bg | 7.56 | 7.56 | 4.5 |
| panel-muted/panel-row | 5.62 | 5.62 | 4.5 |
| panel-label/panel-bg | 7.56 | 7.56 | 4.5 |
| panel-label/panel-row | 5.62 | 5.62 | 4.5 |
| panel-tile-text/tile-bg | 7.56 | 7.56 | 4.5 |
| footer-text/footer-bg | 11.41 | 13.36 | 4.5 |
| footer-muted/footer-bg | 8.36 | 9.79 | 4.5 |
| footer-link/footer-bg | 16.90 | 19.79 | 4.5 |
| footer-accent/footer-bg | 8.27 | 9.68 | 3 |
| mark-text/mark-bg | 6.51 | 6.54 | 4.5 |
| mark-line/mark-bg | 1.58 | 2.35 | 1.0 |
| badge-text/badge-bg | 9.24 | 6.69 | 4.5 |
| win-text/win-bg | 6.46 | 8.13 | 4.5 |
| rank-text/rank-bg | 9.24 | 8.90 | 4.5 |
| rank-1-text/rank-1-bg | 11.15 | 9.16 | 4.5 |
| on-accent/button-bg | 11.15 | 9.16 | 4.5 |
| button-bg/bg (non-text) | 10.32 | 9.16 | 3 |
| score-text/score-bg | 11.15 | 11.15 | 4.5 |
| score-dim/score-bg | 7.56 | 7.56 | 4.5 |
| won-line/score-bg (non-text) | 11.15 | 11.15 | 3 |
| bar-fill/bar-track | 9.08 | 6.27 | 3 |
| bar-lead/lead-track | 6.43 | 5.59 | 3 |
| team-1/surface | 5.88 | 4.39 | 3 |
| team-2/surface | 5.05 | 5.32 | 3 |
| team-3/surface | 8.39 | 6.49 | 3 |
| team-4/surface | 7.38 | 6.57 | 3 |
| team-5/surface | 3.63 | 9.20 | 3 |
| team-6/surface | 6.16 | 10.44 | 3 |

### Achieved vs approved

| role | approved | achieved | dE |
|---|---|---|---|
| nav-bg | #2A4A82 | #2D497A | 1.3 |
| panel-bg | #1F3A68 | #1D3A6E | 1.1 |
| link | #9DB6E8 | #AAB6CC | 4.3 |
| rank-1-bg | #9DB6E8 | #AAB6CC | 4.3 |
| nav-muted | #CDD6EA | #CED5E2 | 1.1 |
| panel-line | #34548A | #395482 | 1.4 |
| rank-bg | #22304D | #192D51 | 1.8 |
| rank-text | #C9D6F2 | #C9D1DF | 2.6 |
| hot | #FF8A9A | #DA9B9C | 6.9 |
| mark-text | #FF8A9A | #DA9B9C | 6.9 |
| mark-bg | #4A1622 | #510915 | 2.7 |
| mark-line | #A23A4E | #A93643 | 2.0 |
| mark-bg | #FBE3E7 | #F7E5E4 | 0.9 |
| mark-line | #E8A9B4 | #E2AEAF | 1.9 |
| mark-text | #A50D26 | #9E1B32 | 1.9 |
| rank-bg | #E6EAF3 | #E6EAF0 | 0.4 |
| panel-muted | #CDD6EA | #CED5E2 | 1.1 |

## Scoreboard

### Role values (resolved, default league colour)

| role | light | dark | league-driven |
|---|---|---|---|
| `bg` | #FFFFFF | #121212 |  |
| `bg-image` | none | none |  |
| `surface` | #FFFFFF | #1A1A1A |  |
| `surface-2` | #F2F2F2 | #232323 |  |
| `line` | #DDDDDD | #333333 |  |
| `line-strong` | #111111 | #E8E8E8 |  |
| `text` | #111111 | #F2F2F2 |  |
| `muted` | #555555 | #A8A8A8 |  |
| `link` | #111111 | #F2A39A | yes |
| `link-hover` | #CB0E1D | #FFFFFF | yes |
| `accent` | #111111 | #F2F2F2 |  |
| `hot` | #CB0E1D | #F2A39A | yes |
| `rule` | #111111 | #E8E8E8 |  |
| `focus` | #CB0E1D | #FFC233 | yes |
| `button-bg` | #CB0E1D | #CF2528 | yes |
| `on-accent` | #FFFFFF | #FFFFFF |  |
| `header-bg` | #CB0E1D | #CF2528 | yes |
| `header-text` | #FFFFFF | #FFFFFF |  |
| `header-muted` | #FEEFED | #FEEFED | yes |
| `header-line` | transparent | transparent |  |
| `header-button-line` | #FFFFFFB3 | #FFFFFFB3 |  |
| `tab` | #FFC233 | #FFC233 | yes |
| `nav-bg` | transparent | transparent |  |
| `nav-text` | #FFFFFF | #FFFFFF |  |
| `nav-muted` | #FEEFED | #FEEFED | yes |
| `panel-bg` | #111111 | #1A1A1A |  |
| `panel-text` | #FFFFFF | #FFFFFF |  |
| `panel-muted` | #9A9A9A | #9A9A9A |  |
| `panel-label` | #9A9A9A | #9A9A9A |  |
| `panel-row` | #000000 | #000000 |  |
| `panel-line` | #2A2A2A | #333333 |  |
| `panel-tile-bg` | #000000 | #000000 |  |
| `panel-tile-text` | #FFC233 | #FFC233 |  |
| `footer-bg` | #111111 | #000000 |  |
| `footer-text` | #BBBBBB | #BBBBBB |  |
| `footer-muted` | #9A9A9A | #9A9A9A |  |
| `footer-link` | #FFFFFF | #FFFFFF |  |
| `footer-line` | #2A2A2A | #2A2A2A |  |
| `footer-accent` | #CB0E1D | #CF2528 | yes |
| `mark-bg` | #000000 | #000000 |  |
| `mark-text` | #FFC233 | #FFC233 |  |
| `mark-line` | #FFC233 | #FFC233 |  |
| `won-line` | #FFC233 | #FFC233 |  |
| `blank-bg` | #F2F2F2 | #232323 |  |
| `badge-bg` | #111111 | #000000 |  |
| `badge-text` | #FFC233 | #FFC233 |  |
| `win-bg` | #FFC233 | #FFC233 |  |
| `win-text` | #111111 | #111111 |  |
| `rank-bg` | #F2F2F2 | #232323 |  |
| `rank-text` | #111111 | #F2F2F2 |  |
| `rank-1-bg` | #111111 | #000000 |  |
| `rank-1-text` | #FFC233 | #FFC233 |  |
| `bar-track` | #DDDDDD | #3A3A3A |  |
| `bar-fill` | #111111 | #E8E8E8 |  |
| `bar-lead` | #FFC233 | #FFC233 |  |
| `score-bg` | #000000 | #000000 |  |
| `score-text` | #FFC233 | #FFC233 |  |
| `score-dim` | #8A8A8A | #8A8A8A |  |
| `score-line` | #333333 | #333333 |  |

League-driven roles (written with league helpers): `link`, `link-hover`, `hot`, `focus`, `button-bg`, `header-bg`, `header-muted`, `tab`, `nav-muted`, `footer-accent`

### Contrast (WCAG ratios, lowest per pair; header pairs use the stops the text sits on)

| pair | light | dark | need |
|---|---|---|---|
| text/bg | 18.88 | 16.73 | 4.5 |
| text/surface | 18.88 | 15.55 | 4.5 |
| text/surface-2 | 16.87 | 14.04 | 4.5 |
| muted/bg | 7.46 | 7.88 | 4.5 |
| muted/surface | 7.46 | 7.32 | 4.5 |
| muted/surface-2 | 6.66 | 6.61 | 4.5 |
| link/bg | 18.88 | 9.35 | 4.5 |
| link/surface | 18.88 | 8.69 | 4.5 |
| link/surface-2 | 16.87 | 7.84 | 4.5 |
| link-hover/bg | 5.80 | 18.73 | 4.5 |
| link-hover/surface | 5.80 | 17.40 | 4.5 |
| link-hover/surface-2 | 5.18 | 15.72 | 4.5 |
| accent/bg | 18.88 | 16.73 | 4.5 |
| accent/surface | 18.88 | 15.55 | 4.5 |
| accent/surface-2 | 16.87 | 14.04 | 4.5 |
| hot/bg | 5.80 | 9.35 | 4.5 |
| hot/surface | 5.80 | 8.69 | 4.5 |
| hot/surface-2 | 5.18 | 7.84 | 4.5 |
| rule/surface | 18.88 | 14.20 | 3 |
| focus/bg | 5.80 | 11.61 | 3 |
| focus/surface | 5.80 | 10.79 | 3 |
| header-text/header | 5.80 | 5.32 | 4.5 |
| header-muted/header | 5.19 | 4.76 | 4.5 |
| tab/header | 3.60 | 3.30 | 3 |
| header-button-line/header | 3.37 | 3.26 | 3 |
| nav-text/nav | 5.80 | 5.32 | 4.5 |
| nav-muted/nav | 5.19 | 4.76 | 4.5 |
| tab/nav | 3.60 | 3.30 | 3 |
| panel-text/panel-bg | 18.88 | 17.40 | 4.5 |
| panel-text/panel-row | 21.00 | 21.00 | 4.5 |
| panel-muted/panel-bg | 6.71 | 6.19 | 4.5 |
| panel-muted/panel-row | 7.46 | 7.46 | 4.5 |
| panel-label/panel-bg | 6.71 | 6.19 | 4.5 |
| panel-label/panel-row | 7.46 | 7.46 | 4.5 |
| panel-tile-text/tile-bg | 13.02 | 13.02 | 4.5 |
| footer-text/footer-bg | 9.84 | 10.94 | 4.5 |
| footer-muted/footer-bg | 6.71 | 7.46 | 4.5 |
| footer-link/footer-bg | 18.88 | 21.00 | 4.5 |
| footer-accent/footer-bg | 3.25 | 3.95 | 3 |
| mark-text/mark-bg | 13.02 | 13.02 | 4.5 |
| mark-line/mark-bg | 13.02 | 13.02 | 1.0 |
| badge-text/badge-bg | 11.70 | 13.02 | 4.5 |
| win-text/win-bg | 11.70 | 11.70 | 4.5 |
| rank-text/rank-bg | 16.87 | 14.04 | 4.5 |
| rank-1-text/rank-1-bg | 11.70 | 13.02 | 4.5 |
| on-accent/button-bg | 5.80 | 5.32 | 4.5 |
| button-bg/bg (non-text) | 5.80 | 3.52 | 3 |
| score-text/score-bg | 13.02 | 13.02 | 4.5 |
| score-dim/score-bg | 6.08 | 6.08 | 4.5 |
| won-line/score-bg (non-text) | 13.02 | 13.02 | 3 |
| bar-fill/bar-track | 13.90 | 9.28 | 3 |
| bar-lead/lead-track | 7.83 | 7.83 | 3 |
| team-1/surface | 5.25 | 6.24 | 3 |
| team-2/surface | 4.77 | 8.47 | 3 |
| team-3/surface | 3.68 | 8.28 | 3 |
| team-4/surface | 5.13 | 8.09 | 3 |
| team-5/surface | 7.38 | 6.51 | 3 |
| team-6/surface | 6.16 | 10.80 | 3 |

### Achieved vs approved

| role | approved | achieved | dE |
|---|---|---|---|
| header-bg | #2B7539 | #387141 | 2.2 |
| button-bg | #2B7539 | #387141 | 2.2 |
| footer-accent | #2B7539 | #387141 | 2.2 |
| link | #6FCF7F | #A0BBA2 | 10.0 |
| hot | #6FCF7F | #A0BBA2 | 10.0 |
| header-muted | #E3EEDF | #EEF3EE | 2.7 |
| header-muted | #FFE5E7 | #FEEFED | 2.4 |
| hot | #CB0E1D | #CB0E1D | 0.0 |

## Deviations from the approved mockups (and why)

| layout | role | mockup | now | ratio | why |
|---|---|---|---|---|---|
| basketball | `hot` (light) | #FF5C66 (leader tile top edge) | #B74047 = league-2 colour mixed 22% toward black | 5.47 on surface (coral was 3.0) | `hot` is also text (stolen-end style), so it must pass 4.5. The coral stays exact in `tab`, `won-line`, `footer-accent` and in dark `hot`. The tile edge in light is therefore a deeper coral than the mockup. |
| basketball | `header-button-line` | #FFFFFF40 | #FFFFFF73 | 3.42 on #032F98 (was 1.96) | ring round the theme button; raised to 3:1 so the control boundary passes (the icon alone already passes) |
| scoreboard | `header-button-line` | #FFFFFF66 (basketball variant) | #FFFFFFB3 | 3.37 on red (was 1.84) | same reason |
| scoreboard | `header-muted`, `nav-muted` | #FFE5E7 (red) / #E3EEDF (green): about 88% white | white mixed 92% over the league colour (#FEEFED on red) | 5.19 light, 4.76 dark | at 88% the lifted dark red gave 4.46:1 (< 4.5) |
| basketball | dark `header-muted` | docs keep #9AA6C4 for text on the page | #B8C3E0 (as dark-palettes.md says) | 5.91 on the lightest text stop #1E3C81 | not a change from the palette doc, listed because #9AA6C4 would be ~4.4 |
| classic | `won-line` | none in the mockup (bold digit instead) | white (`league-ink`) on the league-colour score panel | 11.15 on navy | pair with Classic's white tab underline; if the line score sits on a white card the part should use bold only |

Mockup colours that were NOT changed but are close to the limit: basketball light `muted` on `surface-2` 5.18; classic light team-5 amber #B07D00 chip on white 3.63:1 (chip is never the only carrier); scoreboard dark `button-bg` on page 3.52 (button text is white on it, 5+).

Derived (league-helper) dark values that are less saturated than the hand-picked ones (see "Achieved vs approved"): Classic text accent #AAB6CC vs #9DB6E8; Basketball link #9AB1DC vs #8FB0FF; Scoreboard dark link / hot with the mockup's green #A0BBA2 vs #6FCF7F (dE 10: mixing with white cannot add chroma; with the default red the value is #F2A39A, contrast above 7). All pass AA. If the lead wants the hand-picked values back they can be a `league_color_dark` entry in `league.yml`, not a layout change.

## Roles the mockups have no equivalent for (what I chose)

- **basketball** `mark-bg/-text/-line`: no stolen-end in basketball. Coral wash / deep coral text / coral line from league colour 2 (light), dark red-brown wash with pink text (dark). `blank-bg` = `surface-2`. `badge-*`: league wash with league text (light), league colour mixed into the surface with tinted text (dark). `win-*` = green chip (#DDF1E0 / #17602A, dark #17361F / #8FDC9A). `rank-bg` and `rank-1-bg` are `transparent` (the mockup shows plain numerals): `rank-text` = muted, `rank-1-text` = accent. `panel-tile-*` = league wash with the darkened league colour. `bar-*`: track = line, fill = league colour, lead = `hot`. `header-line` and `nav-bg` transparent (nav sits inside the header gradient).
- **classic** `bar-lead` = league colour 2; `panel-tile-bg` transparent with the muted panel text (the mockup's sheet label is plain text); `header-button-line` transparent (the mockup button has no ring); `score-*` = white on the league colour panel (same as the next-game panel); `win-*` green chip as in basketball. The dark nav bar's bottom edge (#3A5C98 in the mockup) has no role and is not reproduced (`header-line` is the page header's edge).
- **scoreboard** `link` in light is ink #111 (the mockup's links are ink, bold), and `accent` is ink too (big numbers are ink; amber on white would fail), amber only on black digit cells; `hot` = league colour (also hover colour of links); `panel-*` = the black "game of the week" card / "next up" header strip (#111 light, #1A1A1A dark card); `panel-row` = the black digit cell inside it; `rank-bg` / `rank-1-bg` = the race row and lead-row backgrounds (#F2F2F2 / #111 light, #232323 / #000 dark); `blank-bg` = `surface-2`; `team-*` see Decisions. `focus` is the league colour in light, amber in dark.
- No ticker roles exist in the table. Suggestion for the shell parts: the Scoreboard ticker uses `footer-bg` (#111 / #000, the mockup's ticker colour), `footer-link` for the score text, `score-text` (amber) for the "Final" tag, `footer-muted` for the "bye" item and the `|` separators.

## Notes for the other agents / the lead

- **Focus ring over the header**: `--st-focus` is chosen for the page bg and surfaces (>= 3:1 on both). On the coloured header or nav bar a ring in that colour can vanish (Basketball light: navy ring on navy; Scoreboard light: red ring on the red header). The shell parts should draw the focus ring in `--st-header-text` inside `.st-header` / `.st-nav` (and in `--st-panel-text` on the panel).
- **Basketball footer**: the footer scene carries the page colour in its own image, so `footer-bg` can be painted on `.st-footer` or on `.st-footer__body`; both look right. (If it is on `.st-footer`, the scene box covers it with the page colour, as in the mockup.)
- **Basketball header**: the scene div must be the last child, full width, so the `margin-top: 6px` plus 56 px bring the hills to the bottom of the gradient (the gradient stops 58/74/88/100% assume a header of about 178 px on a phone). On desktop (stage 9) the stops are percentages of a shorter header; the sunrise will then sit closer to the nav row: adjust the `header-bg` percentages there if needed.
- **Header text over the gradient**: contrast is checked on the stops text sits on (Basketball light 0/58/74%, dark 0/50/76%). Nothing readable should be placed in the lower 25% of the header.
- **League colour limits**: every league-coloured surface carries white text (`league-ink`), and every dark-mode surface derived with `league-lift` / `league-dim` is checked only for the default colour here. `--st-league-lift` for Scoreboard (4%) and Classic (8%) is small on purpose: a mid-tone league colour that passes white at 4.5 stays above 4.5 after the lift in most cases, but stage 4's data check should test the derived dark value, as docs/design.md already says. Scoreboard `header-muted` (92% white) needs a league colour whose dark version is no lighter than the default red.
- Light `link-hover` for Basketball and Classic is the ink #0B1B3F; for Scoreboard it is the league colour.
- Colour-mix percentages written inline in the layout files (in the mark, badge, rank, `header-bg`, muted-on-colour roles) are the fitted values: e.g. `color-mix(in oklab, var(--st-league-base), white 80%)` is "muted text on a league-coloured surface".

## NEW roles needed that are not in docs/design.md

None. Everything is written with existing roles. (Suggested for the contract by the shell/parts agents, not added: ticker bg/text/tag/sep for Scoreboard, see above; and an optional `nav-line` for Classic's dark nav bottom edge.)


---

# layouts-B notes: curling, hockey, slopitch

Files: assets/css/layouts/curling.css, hockey.css, slopitch.css. Written from a throwaway
generator in the scratchpad (lb/spec.py, emit.py), which also resolved every value
(oklab mixes) and checked contrast; the generator is not in the repo. Verified: braces
balanced, the media-query dark block and the [data-theme="dark"] block hold identical
declarations (compared by script), every role of the design.md table is defined in the light
block of each file (roles equal to the tokens.css default binding are omitted on purpose:
hockey `fs-title`, slopitch `fs-h2`, `fs-stat`). Scenes were rendered in Chromium at 390 and
1440 px, light and dark, OS-preference and `data-theme` (the two dark paths render identically).

## Decisions and changes of mind

* **Curling league colour 2 (house red)** drives: header line, stolen-end text/tint/border
  (`hot`, `mark-*`). The mockup's #A50D26 stolen-end text and #FBE3E7 / #E8A9B4 tint are
  written as `color-mix(in oklab, var(--st-layout-accent-base), black 13% | white 87% | white 20%)`
  so a league colour 2 recolours them (achieved #A60B24 / #FDE4E3 / #D95658).
* **Curling `rule`**: the light mockup's 2 px table rule is ink #0E2233; I followed the brief
  (rules = league blue), so light `rule` = `league-base`. The dark mockup already uses the accent
  blue. `score-line` (total-cell divider on the line score) stays ink in light (mockup).
* **Curling ink panel/header/footer** stay literal in both themes (sport ground), also the
  dark panel #16324F; so `league-dim` and `league-wash` are only used for `badge-bg`.
* **Hockey**: league colour = blue (links, `rule`, goalie edge, buttons, WIN badge), league
  colour 2 = kickplate gold (header bar, tab, panel label, footer strip, GWG badge, rank-1).
  Boards, red line, ice, ink, `hot` red (#C8102E / dark #FF6B7A) stay literal. Gold is never used
  as text on light (only on the near-black boards and as a fill with #14181F text).
  `accent` is ink (the mockup's big numbers are text-coloured, not blue).
* **Slo-pitch**: league colour = green (header, panel, links, `accent`, buttons, WIN badge, rank-1),
  colour 2 = clay (tile edge, `hot`, limit mark). `rule` is literal ink (#22201C) / chalk
  (#D9CFB6) as in the mockups, not league-driven. Footer ink stays literal.
* **Slo-pitch scene arc is baked** (#B5532E light, #C4643C dark, plus the page colour of the cream
  band): a league that changes colour 2 recolours tile edges and limit marks but not the arc,
  because an SVG data URI cannot read CSS variables. A stage 4 step could rewrite
  `--st-scene-image` if wanted. The same holds for hockey rink lines and the curling rings
  (curling rings are white only, so unaffected).
* **Scenes are independent of the shell agent's border**: all three scenes are in-flow or
  absolute inside `.st-header` and drawn from my rules only. Two header overrides were needed
  and are in the scene section of the files (shell agent: please do not fight them):
  - curling: `.st-header { position: relative; overflow: hidden; isolation: isolate }` (the rings
    are `z-index:-1` so they sit above the header background and below its content even if the
    shell does not make its rows positioned);
  - hockey: `header.st-header { border-bottom: 0 }` because the strip must come AFTER the gold
    bar and a child of the header cannot sit below the header's own border. The scene draws the
    gold bar itself as `border-top: 6px solid var(--st-header-line)`, then 14 px of rink lines.
    If the shell agent also draws a 6px bottom border on the hockey header, my override removes it.
  - slopitch: `header.st-header { border-bottom: 0 }` (`header-line` is transparent; a transparent
    border would otherwise show the green background under the arc).
* **Scene sizing**: hockey and slopitch pictures are `width='100%'` SVGs (lines/diamond keep their
  px size on desktop; the arc stretches). Curling rings are a fixed 220 px picture at
  `right:-78px; top:-84px`.
* `--st-bg-image`: curling dark = 9 px SVG pebble tile (#CFE6FF at 5%, as `#CFE6FF0D`); slopitch
  dark = the chalk rules `repeating-linear-gradient` (rgba(244,236,214,.045)); everything else `none`.
* `--st-team-lift` (custom team colours, dark only): curling 40%, hockey 40%, slopitch 37% (best
  fit of palette light -> palette dark, mean dE about 8-9; custom colours will not match exactly).
* `--st-scene-image-footer: none` and `.st-footer__scene { display: none }` in all three.
  Hockey's footer kickplate is `--st-footer-accent` (league colour 2).

## Knobs (tuned against the approved dark palette, oklab, default league colours)

| layout | knobs set | why |
|---|---|---|
| curling | `--st-tint: 58%`, `--st-lift: 22%` | tint -> accent #8CB8E8; lift -> button / WIN badge (white text 4.82:1) and the dark red header line |
| hockey | `--st-tint: 55%` | tint -> link/rule blue; defaults for dim/lift/wash |
| slopitch | `--st-dim: 25%`, `--st-tint: 55%`, `--st-lift: 31%` | dim -> dark header #1E4527 (dE 0.7); tint -> green accent; lift is used only on clay (mark text) |

oklab mixing toward white desaturates blues and greens, so the derived accents are paler and greyer
than the approved #8CB8E8 / #8DB8FF / #86CC92 (dE 4-9). Contrast is higher than approved, hue is
slightly off. A stage 4 `league-tint` computed in OKLCH would match better (suggestion only).

## Achieved vs approved dark values (default league colours)

(per layout, at the end of this file, under each role table)


## Deviations from the mockups (contrast) and other changes

| layout | role | mockup | now | ratio before -> after |
|---|---|---|---|---|
| slopitch | `panel-row` | #FFFFFF1F | #FFFFFF14 | needed so text inside the rows passes |
| slopitch | `panel-muted` | #E3EEDF | #F1F7EE | 4.06 -> 4.89 on the row over green |
| slopitch | `panel-label` ("Diamond 1", "Next game day") | #F3E3C3 / #E3EEDF | #FBF0D9 | 3.83 -> 4.71 on the row |
| slopitch | team-4 (Line Drives chip) | #C98A12 | #BE8210 | 2.76 -> 3.07 vs page bg (3:1 for the chip) |
| curling | `mark-line` light | #E8A9B4 | derived #D95658 | 1.95 -> 3.87 vs surface (meaning-carrying swatch/border) |
| curling | `header-line` (red) on ink | #C8102E | unchanged | 2.76:1, decorative border, no text; kept as approved. Dark: 3.9+ |
| curling | `rule` light | ink #0E2233 | league blue #1D4E89 | brief decision, 8.4:1 on white |
| hockey | `mark-line` | none in mockup | gold darkened 30% (#966700) | gold #F2A900 on white is 2.0 |
| slopitch | `bar-fill` | none in mockup | #867B66 | 3.08 vs the track |

Other pairs that already passed AA (all text >= 4.5, non-text >= 3) in both themes: text, muted,
link, link-hover, accent, hot on bg/surface/surface-2; header/nav/tab on header-bg; panel text,
muted and label on panel-bg and on the row; footer text/muted/link; mark-text, badge, win, rank,
rank-1, on-accent/button-bg, score-text/score-dim on score-bg; all 6 team chips vs surface and bg.
`nav-bg` is transparent in these layouts, so nav colours were checked against `header-bg`.

## Roles with no mockup equivalent (what I chose)

* curling: `surface-2`, `line-strong`, `blank-bg`, `rank-*`, `bar-*`, `badge-*`, `win-*` (all
  themes) and the dark game-page colours (`score-bg` dark #16324F = the panel, `score-line` dark = tint,
  `blank-bg` dark #1A2D3D, `surface-2` dark #1A2D3D); the dark mockup's standings table renders with
  light cells (a mockup glitch), the specified dark palette (#13222F cards) was used instead.
  `panel-line` light = transparent (light panel has no border). `footer-accent` = transparent.
* hockey: `mark-*` (no scoring highlight mocked: pale gold fill / ink text / darkened-gold line in light,
  very dark gold / gold text / gold line in dark), `panel-tile-*` (white tile, ink text; hockey has no
  tile), `surface-2` dark #2A3646, `line-strong` (#C3CAD4 / #4A5A70), `bar-*`, `blank-bg`,
  `win-*` (league blue / lift, white text), `score-*` dark (#090B0F cells, `score-line` #334255).
  `score-bg` is the black T column and the FINAL tag (#14181F), `score-dim` the loser total #D7DCE3.
  `hot` is the red used for the goalie tile edge (the shell agent should use `--st-hot` for the second tile edge).
* slopitch: `mark-bg` = transparent (the limit mark is a circled/underlined number, no tint),
  `panel-tile-*` (cream #F3E3C3 with ink; the mockup has no tile, the diamond label is cream text),
  `badge-*`, `rank-*` (paper tones #F3EBDA / #EAE0C9), `bar-*`, `blank-bg`, `surface-2` dark #2B2820,
  `win-bg` (league green, white text, same in dark), `score-*` (no dark final panel: the score block sits on
  the white/dark card, `score-bg` = surface, `score-text` = text, `score-dim` = muted, `score-line` =
  the grid colour #CFC3A8 / #57503F), `won-line`.
  `header-line` = transparent (no line under the green header).

## New roles needed

None. Used inline `color-mix(in oklab, var(--st-layout-accent-base), white|black N%)` (and one
`color-mix(var(--st-league-dim), black 8%)`) in role values for second-colour tints and shades;
if the checker only resolves the declared helpers, either teach it `color-mix()` over helpers or add
`--st-league-2-dim`, `--st-league-2-lift`, `--st-league-2-wash` to tokens.css and I will swap them in.
Places: curling `hot`/`mark-*`/`header-line` (dark), slopitch `hot`/`mark-text`/`mark-line`/`panel-bg`
(dark), hockey `mark-bg`/`mark-line`. `var(--st-lift)` is used as the percentage inside some of them.

## Role tables (resolved hex with default league colours; "league-driven" shows the expression)

### curling

| role | light | dark | league-driven (light / dark expression) |
|---|---|---|---|
| bg | #EEF4F8 | #0B1620 |  |
| bg-image | none | url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='9' height='9'><circle cx='4.5' cy='4.5' r='1' fill='%23CFE6FF' fill-opacity='.05'/></svg>") |  |
| surface | #FFFFFF | #13222F |  |
| surface-2 | #F4F7FA | #1A2D3D |  |
| line | #D5E0EA | #24394B |  |
| line-strong | #C9D3DD | #34506A |  |
| text | #0E2233 | #E8F0F6 |  |
| muted | #4F5D6B | #9DB0C2 |  |
| link | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| link-hover | #0E2233 | #E8F0F6 |  |
| accent | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| hot | #A60B24 | #EB8D8A | `mix(2-base), black 13%)` / `mix(2-base), white 45%)` |
| rule | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| focus | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| button-bg | #1D4E89 | #4E74A4 | `base)` / `lift)` |
| on-accent | #FFFFFF | #FFFFFF | `ink)` |
| header-bg | #0E2233 | #060D15 |  |
| header-text | #FFFFFF | #FFFFFF |  |
| header-muted | #C5D3E2 | #C5D3E2 |  |
| header-line | #C8102E | #DB5A5C | `2-base)` / `mix(2-base), white lift))` |
| header-button-line | #FFFFFF40 | #FFFFFF40 |  |
| tab | #FFFFFF | #FFFFFF |  |
| nav-bg | transparent | transparent |  |
| nav-text | #FFFFFF | #FFFFFF |  |
| nav-muted | #C5D3E2 | #C5D3E2 |  |
| panel-bg | #0E2233 | #16324F |  |
| panel-text | #FFFFFF | #FFFFFF |  |
| panel-muted | #C5D3E2 | #C5D3E2 |  |
| panel-label | #C5D3E2 | #C5D3E2 |  |
| panel-row | #FFFFFF1F | #FFFFFF1F |  |
| panel-line | transparent | #2A4D70 |  |
| panel-tile-bg | #FFFFFF | #F2F6FA |  |
| panel-tile-text | #0E2233 | #0B1620 |  |
| footer-bg | #0E2233 | #060D15 |  |
| footer-text | #FFFFFF | #FFFFFF |  |
| footer-muted | #C5D3E2 | #C5D3E2 |  |
| footer-link | #FFFFFF | #FFFFFF |  |
| footer-line | #FFFFFF26 | #FFFFFF26 |  |
| footer-accent | transparent | transparent |  |
| mark-bg | #FDE4E3 | #53030D | `mix(2-base), white 87%)` / `mix(2-base), black 47%)` |
| mark-text | #A60B24 | #EB8D8A | `mix(2-base), black 13%)` / `mix(2-base), white 45%)` |
| mark-line | #D95658 | #D85154 | `mix(2-base), white 20%)` / `mix(2-base), white 18%)` |
| won-line | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| blank-bg | #EEF2F6 | #1A2D3D |  |
| badge-bg | #E7ECF3 | #0E2D53 | `wash)` / `dim)` |
| badge-text | #0E2233 | #E8F0F6 |  |
| win-bg | #1D4E89 | #4E74A4 | `base)` / `lift)` |
| win-text | #FFFFFF | #FFFFFF | `ink)` |
| rank-bg | #E3ECF4 | #24394B |  |
| rank-text | #0E2233 | #E8F0F6 |  |
| rank-1-bg | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| rank-1-text | #FFFFFF | #0B1620 | `ink)` / `#0B1620` |
| bar-track | #D5E0EA | #24394B |  |
| bar-fill | #56636F | #9DB0C2 |  |
| bar-lead | #1D4E89 | #9DB2CE | `base)` / `tint)` |
| score-bg | #0E2233 | #16324F |  |
| score-text | #FFFFFF | #FFFFFF |  |
| score-dim | #C5D3E2 | #C5D3E2 |  |
| score-line | #0E2233 | #9DB2CE | `#0E2233` / `tint)` |

teams light: ['#56636F', '#C8102E', '#2E7D4F', '#6B3FA0', '#1D4E89', '#B07D00'] 
teams dark: ['#C3CDD7', '#E8475A', '#34A464', '#B391EE', '#6FA3EA', '#E9B940']

Achieved vs approved (dark):
- link: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- accent: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- rule: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- focus: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- hot: achieved #EB8D8A vs approved #FF8A9A (dE 4.2)
- mark-text: achieved #EB8D8A vs approved #FF8A9A (dE 4.2)
- header-line: achieved #DB5A5C vs approved #E5354F (dE 5.5)
- mark-bg: achieved #53030D vs approved #4A1622 (dE 3.7)
- mark-line: achieved #D85154 vs approved #A23A4E (dE 12.3)
- button-bg: achieved #4E74A4 vs approved #3D7CC9 (dE 5.7)
- panel-bg: achieved #16324F vs approved #16324F (dE 0.0)
- panel-line: achieved #2A4D70 vs approved #2A4D70 (dE 0.0)
- rank-1-bg: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- bar-lead: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- won-line: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)
- score-line: achieved #9DB2CE vs approved #8CB8E8 (dE 3.9)

### hockey

| role | light | dark | league-driven (light / dark expression) |
|---|---|---|---|
| bg | #F6F8FA | #17202B |  |
| bg-image | none | none |  |
| surface | #FFFFFF | #212C39 |  |
| surface-2 | #EDF1F5 | #2A3646 |  |
| line | #DCE2EA | #334255 |  |
| line-strong | #C3CAD4 | #4A5A70 |  |
| text | #151A22 | #EEF2F7 |  |
| muted | #5A6478 | #A3AEBD |  |
| link | #1D4E89 | #96ADCB | `base)` / `tint)` |
| link-hover | #14181F | #FFFFFF |  |
| accent | #151A22 | #EEF2F7 |  |
| hot | #C8102E | #FF6B7A |  |
| rule | #1D4E89 | #96ADCB | `base)` / `tint)` |
| focus | #1D4E89 | #96ADCB | `base)` / `tint)` |
| button-bg | #1D4E89 | #386298 | `base)` / `lift)` |
| on-accent | #FFFFFF | #FFFFFF | `ink)` |
| header-bg | #14181F | #090B0F |  |
| header-text | #FFFFFF | #FFFFFF |  |
| header-muted | #B8C0CC | #B8C0CC |  |
| header-line | #F2A900 | #F2A900 | `2-base)` |
| header-button-line | #FFFFFF40 | #FFFFFF40 |  |
| tab | #F2A900 | #F2A900 | `2-base)` |
| nav-bg | transparent | transparent |  |
| nav-text | #FFFFFF | #FFFFFF |  |
| nav-muted | #C3CAD4 | #C3CAD4 |  |
| panel-bg | #14181F | #090B0F |  |
| panel-text | #FFFFFF | #FFFFFF |  |
| panel-muted | #B8C0CC | #B8C0CC |  |
| panel-label | #F2A900 | #F2A900 | `2-base)` |
| panel-row | #FFFFFF14 | #FFFFFF14 |  |
| panel-line | transparent | #334255 |  |
| panel-tile-bg | #FFFFFF | #FFFFFF |  |
| panel-tile-text | #14181F | #14181F |  |
| footer-bg | #14181F | #090B0F |  |
| footer-text | #FFFFFF | #FFFFFF |  |
| footer-muted | #B8C0CC | #B8C0CC |  |
| footer-link | #FFFFFF | #FFFFFF |  |
| footer-line | #FFFFFF26 | #FFFFFF26 |  |
| footer-accent | #F2A900 | #F2A900 | `2-base)` |
| mark-bg | #FEF3E2 | #190E00 | `mix(2-base), white 85%)` / `mix(2-base), black 78%)` |
| mark-text | #151A22 | #F2A900 | `#151A22` / `2-base)` |
| mark-line | #966700 | #F2A900 | `mix(2-base), black 30%)` / `2-base)` |
| won-line | #1D4E89 | #96ADCB | `base)` / `tint)` |
| blank-bg | #EDF1F5 | #2A3646 |  |
| badge-bg | #F2A900 | #F2A900 | `2-base)` |
| badge-text | #14181F | #14181F |  |
| win-bg | #1D4E89 | #386298 | `base)` / `lift)` |
| win-text | #FFFFFF | #FFFFFF | `ink)` |
| rank-bg | #EDF1F5 | #2E3A4B |  |
| rank-text | #14181F | #EEF2F7 |  |
| rank-1-bg | #F2A900 | #F2A900 | `2-base)` |
| rank-1-text | #14181F | #14181F |  |
| bar-track | #DCE2EA | #334255 |  |
| bar-fill | #5A6478 | #A3AEBD |  |
| bar-lead | #1D4E89 | #96ADCB | `base)` / `tint)` |
| score-bg | #14181F | #090B0F |  |
| score-text | #FFFFFF | #FFFFFF |  |
| score-dim | #D7DCE3 | #D7DCE3 |  |
| score-line | #3A4250 | #334255 |  |

teams light: ['#C8102E', '#1D4E89', '#2F6B3A', '#0E7C8A', '#6B7280', '#A8561C'] 
teams dark: ['#FF6B7A', '#6FA8FF', '#4FB164', '#7FDDE6', '#8E96A3', '#F0965A']

Achieved vs approved (dark):
- link: achieved #96ADCB vs approved #8DB8FF (dE 7.3)
- rule: achieved #96ADCB vs approved #6FA8FF (dE 9.1)
- focus: achieved #96ADCB vs approved #8DB8FF (dE 7.3)
- won-line: achieved #96ADCB vs approved #6FA8FF (dE 9.1)
- bar-lead: achieved #96ADCB vs approved #6FA8FF (dE 9.1)

### slopitch

| role | light | dark | league-driven (light / dark expression) |
|---|---|---|---|
| bg | #FBF7EE | #131A14 |  |
| bg-image | none | repeating-linear-gradient(180deg, transparent 0, transparent 27px, rgba(244, 236, 214, 0.045) 27px, rgba(244, 236, 214, 0.045) 28px) |  |
| surface | #FFFFFF | #22201A |  |
| surface-2 | #F8F2E4 | #2B2820 |  |
| line | #E6DDC8 | #3A362C |  |
| line-strong | #CFC3A8 | #57503F |  |
| text | #22201C | #F4ECD9 |  |
| muted | #5E574B | #BDB29C |  |
| link | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| link-hover | #22201C | #FFFFFF |  |
| accent | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| hot | #964324 | #D08970 | `mix(2-base), black 13%)` / `mix(2-base), white lift))` |
| rule | #22201C | #D9CFB6 |  |
| focus | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| button-bg | #2F6B3A | #2F6B3A | `base)` |
| on-accent | #FFFFFF | #FFFFFF | `ink)` |
| header-bg | #2F6B3A | #1D4624 | `base)` / `dim)` |
| header-text | #FFFFFF | #FFFFFF |  |
| header-muted | #E3EEDF | #E3EEDF |  |
| header-line | transparent | transparent |  |
| header-button-line | #FFFFFF55 | #FFFFFF55 |  |
| tab | #F3E3C3 | #F3E3C3 |  |
| nav-bg | transparent | transparent |  |
| nav-text | #FFFFFF | #FFFFFF |  |
| nav-muted | #E3EEDF | #E3EEDF |  |
| panel-bg | #2F6B3A | #193E1F | `base)` / `mix(dim), black 8%)` |
| panel-text | #FFFFFF | #FFFFFF |  |
| panel-muted | #F1F7EE | #F1F7EE |  |
| panel-label | #FBF0D9 | #FBF0D9 |  |
| panel-row | #FFFFFF14 | #FFFFFF14 |  |
| panel-line | transparent | #2F6B3A | `transparent` / `base)` |
| panel-tile-bg | #F3E3C3 | #F3E3C3 |  |
| panel-tile-text | #22201C | #22201C |  |
| footer-bg | #22201C | #0B0F0B |  |
| footer-text | #FFFFFF | #FFFFFF |  |
| footer-muted | #C9C0AD | #C9C0AD |  |
| footer-link | #FFFFFF | #FFFFFF |  |
| footer-line | #3A3731 | #2A3326 |  |
| footer-accent | transparent | transparent |  |
| mark-bg | transparent | transparent |  |
| mark-text | #964324 | #D08970 | `mix(2-base), black 13%)` / `mix(2-base), white lift))` |
| mark-line | #B5532E | #D08970 | `2-base)` / `mix(2-base), white lift))` |
| won-line | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| blank-bg | #F3EBDA | #2B2820 |  |
| badge-bg | #EAE0C9 | #3A362C |  |
| badge-text | #22201C | #F4ECD9 |  |
| win-bg | #2F6B3A | #2F6B3A | `base)` |
| win-text | #FFFFFF | #FFFFFF | `ink)` |
| rank-bg | #F3EBDA | #3A362C |  |
| rank-text | #22201C | #F4ECD9 |  |
| rank-1-bg | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| rank-1-text | #FFFFFF | #131A14 | `ink)` / `#131A14` |
| bar-track | #E6DDC8 | #3A362C |  |
| bar-fill | #867B66 | #BDB29C |  |
| bar-lead | #2F6B3A | #A0BBA2 | `base)` / `tint)` |
| score-bg | #FFFFFF | #22201A |  |
| score-text | #22201C | #F4ECD9 |  |
| score-dim | #5E574B | #BDB29C |  |
| score-line | #CFC3A8 | #57503F |  |

teams light: ['#B23A2E', '#5C3F8F', '#2F5DA8', '#BE8210', '#7A5A3A', '#2B8C8C'] 
teams dark: ['#F27463', '#B9A3F0', '#6E98EA', '#F0C04A', '#A8825A', '#5CC7C2']

Achieved vs approved (dark):
- link: achieved #A0BBA2 vs approved #86CC92 (dE 6.5)
- accent: achieved #A0BBA2 vs approved #86CC92 (dE 6.5)
- header-bg: achieved #1D4624 vs approved #1E4527 (dE 0.7)
- panel-bg: achieved #193E1F vs approved #1A3D22 (dE 0.7)
- panel-line: achieved #2F6B3A vs approved #2F5E39 (dE 4.2)
- hot: achieved #D08970 vs approved #E8875E (dE 4.4)
- mark-text: achieved #D08970 vs approved #E8875E (dE 4.4)
- mark-line: achieved #D08970 vs approved #E0835A (dE 3.4)
- rank-1-bg: achieved #A0BBA2 vs approved #86CC92 (dE 6.5)
- focus: achieved #A0BBA2 vs approved #86CC92 (dE 6.5)
