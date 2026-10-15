# Designs

> Stage 3 (design system) is below the canvases: see **The design system** for the files,
> token roles and part anatomy; the parts-by-layout descriptions and the contrast results follow.

## Design canvases
- **scorers-table: layouts** (phone, light, and a dark Home for each layout):
  https://claude.ai/artifact/WUVtsLg2GDS5fVa8KzqJAN
  - an overview board: the six layouts' fonts and colours;
  - sport layouts: Home and Game for basketball, curling, hockey, slo-pitch;
  - general layouts: Classic (with curling, with hockey) and Scoreboard (with
    slo-pitch, with basketball);
  - dark: one Home per layout.
- **The Masters basketball site's directions** (where Classic, Scoreboard and
  the basketball layout come from): https://claude.ai/artifact/BaXVw5DEwLEePb3chLk3c5

The canvases are private to their owner until shared from their Share menu.

## The six layouts

| Layout | Kind | Type | Colours (light) |
|---|---|---|---|
| Basketball | sport | Barlow Condensed + Barlow | deep blue #032F98 header with a sunrise edge, coral #FF5C66 active tab, ink #0B1B3F, page #F4F6FB |
| Curling | sport | Alegreya + Source Sans 3 | pebbled ice #EEF4F8, navy ink #0E2233, house red #C8102E and blue #1D4E89 |
| Hockey | sport | Saira Condensed + Saira | white ice, boards #14181F, red #C8102E and blue #1D4E89 lines, kickplate #F2A900 |
| Slo-pitch | sport | Zilla Slab + Work Sans | scorebook paper #FBF7EE, clay #B5532E, outfield green #2F6B3A, ink #22201C |
| Classic | general | Barlow Condensed + Barlow | white header, one bar in the league's colour, page #F4F6FB |
| Scoreboard | general | Anton + Chakra Petch | black #111111, amber digits #FFC233, header bar in the league's colour |

Dark palettes: [`dark-palettes.md`](dark-palettes.md).

## Decisions so far
- Every layout has light and dark; dark is a colour swap, never a different
  structure.
- One shared desktop grid for all layouts (header on one row, main column of
  about two thirds, side column); layouts only re-skin it. Desktop comes late
  (stage 9).
- Sample leagues are made up: Riverside Masters Basketball, Pine Lake Curling
  Club, Northside Old-Timers Hockey, Maple Park Slo-Pitch.
- The mockups are for reference: rebuild them as clean templates and CSS
  variables; don't copy their inline styles.


---

# The design system (stage 3)

Phone first (360-390 px). Desktop is stage 9. No Jekyll yet: stage 4 turns the
anatomy below into includes.

## Files

```
assets/css/fonts.css        @font-face for the eight families (files in assets/fonts/, self-hosted, OFL)
assets/css/tokens.css       shared scales (type, space, radii, sizes), league-colour maths, team-colour classes
assets/css/layouts/<id>.css one per layout: every colour role for light AND dark, fonts, shape knobs,
                            league/team defaults, header/footer scenes
assets/css/base.css         page root, small pieces (chip, badge, section, card, button, table)
assets/css/parts-shell.css  header, nav, theme button, ticker, footer, page title
assets/css/parts-scores.css result card, final-score panel, line score (4 shapes), event log, roster
assets/css/parts-data.css   standings table + race, leader tile/row, game row, next-game panel, team card
scripts/design_system/      sample data and specimen markup; scripts/build_design_system.py writes
docs/design-system/index.html   (generated: every token and part, six layouts, light and dark)
scripts/check_contrast.py   WCAG AA for every text/background pair; writes docs/contrast.md
```

Stage 4 links `fonts, tokens, layouts/<layout>, base, parts-*` in that order (or
concatenates them). Only the chosen layout's file is needed; the design-system page
loads all six because every rule is scoped to `[data-layout="<id>"]`.

## How a page picks its look

`<html data-layout="curling">`, optionally `data-theme="light|dark"`. With no
`data-theme` the page follows `prefers-color-scheme` (works with JavaScript off);
the sun/moon button sets `data-theme` and saves `st-theme` in `localStorage`.
Each layout file holds its dark values twice (an `@media (prefers-color-scheme: dark)`
block with `:not([data-theme="light"])`, and a `[data-theme="dark"]` block) because
CSS cannot share one declaration between the two; `scripts/check_contrast.py` fails
if the two copies differ. Layout selectors sit on the element carrying
`data-layout`, so the design-system page can place many wrappers side by side.

## Token roles

Every custom property is `--st-<role>`. Parts read roles only; no raw hex in
`base.css` or `parts-*.css`. A layout file gives each role a value for light and for
dark. (Layouts may define extra `--st-*` tokens only if `check_contrast.py --tokens`
can see them used; the lint lists undefined and unused roles.)

| Group | Roles |
|---|---|
| Ground | `bg`, `bg-image` (pebbles, chalk rules; default none), `surface`, `surface-2` (period bands, hover), `line`, `line-strong` |
| Text | `text`, `muted`, `link`, `link-hover`, `accent` (big numbers, rank numbers), `hot` (second accent: stolen-end text, hot tile edge), `rule` (the 2 px rule under table heads), `focus` |
| Buttons | `button-bg`, `on-accent` (text on `button-bg`) |
| Header | `header-bg` (colour or gradient), `header-text`, `header-muted`, `header-line`, `header-button-line`, `tab` (active underline), `nav-bg`, `nav-text`, `nav-muted` (Classic's separate nav bar; others leave `nav-bg` transparent) |
| Panel (next game) | `panel-bg`, `panel-text`, `panel-muted`, `panel-label`, `panel-row`, `panel-line`, `panel-tile-bg`, `panel-tile-text` |
| Footer | `footer-bg`, `footer-text`, `footer-muted`, `footer-link`, `footer-line`, `footer-accent` |
| Marks | `mark-bg`, `mark-text`, `mark-line` (stolen end, run-limit inning, scoring highlight), `won-line` (won-period underline), `blank-bg`, `badge-bg`, `badge-text`, `win-bg`, `win-text` |
| Rank | `rank-bg`, `rank-text`, `rank-1-bg`, `rank-1-text` |
| Bars | `bar-track`, `bar-fill`, `bar-lead` |
| Score board | `score-bg`, `score-text`, `score-dim` (losing side), `score-line` (Scoreboard digits, hockey and curling total cells) |
| Scenes | `scene-image`, `scene-image-footer` (data-URI SVGs, one per theme, no file paths) |
| Team | `team-1` ... `team-6` (tuned per theme), `team-lift` |
| League | inputs `league-color`, `league-color-dark`, `league-color-2`, `league-color-2-dark`; derived `league-base`, `league-dim`, `league-lift`, `league-tint`, `league-wash`, `league-2-base`, `league-2-tint`, `league-ink` |
| Type | `font-display`, `font-body`, `font-num`, `w-display`, `w-strong`, `display-transform`, `display-tracking`, `num-variant`, and the `fs-*` roles bound to the `step-*` scale |
| Shape | `radius-card`, `radius-panel`, `radius-chip`, `radius-sm`, `radius-xs`, `radius-pill`, `border`, `border-strong` |

Scales (rem; px at a 16 px root): type steps 11 12 13 14 15 16 17 20 24 28 32 40 48
56 72; space 2 4 6 8 12 16 24 32 40; radii 4 8 10 12 pill; tap target 44.

## League and team colours

* **League colour**: the league sets `--st-league-color` (and optionally `-dark`,
  `-2`, `-2-dark`) as an inline style on `<html>`; each layout supplies its default.
  Layouts bind the derived helpers to roles (e.g. Classic: nav bar = `league-base`;
  dark text accent = `league-tint`). Text on the league colour is always white;
  stage 4's data check runs the same colour maths in Python and stops, naming
  `league.yml`'s `colour`, if white on it, or the derived dark version, fails AA.
  *(Decided with the user in stage 3: one colour, automatic lift, optional
  `colour_dark`, checked.)*
* **Team colours**: any hex per team. `<span class="st-chip st-team--custom"
  style="--st-team-hex:#D9621A">`; dark mode lifts it by `--st-team-lift`. Teams
  without a colour take palette slot 1-6 (`st-team--N`), tuned per layout and theme.
  The chip never carries information alone: the team's name is always beside it.

## Part anatomy (class names are the contract between CSS, specimens and stage 4)

BEM with an `st-` prefix: `.st-block`, `.st-block__element`, `.st-block--modifier`,
state classes `is-*`. A layout restyles a part through tokens first and a
`[data-layout="<id>"] .st-...` rule only where the mockup differs in shape.

### Shell

```html
<header class="st-header">
  <div class="st-header__top">
    <a class="st-brand" href="#">
      <span class="st-brand__badge" role="img" aria-label="Riverside Masters Basketball badge">RMB</span>
      <span class="st-brand__text">
        <span class="st-brand__name">Riverside Masters</span>
        <span class="st-brand__meta">Basketball · 2026–27</span>
      </span>
    </a>
    <button class="st-theme-toggle" type="button" aria-label="Switch to dark theme"><svg aria-hidden="true">…</svg></button>
  </div>
  <nav class="st-nav" aria-label="Main">
    <a class="st-nav__link" href="#" aria-current="page">Home</a><a class="st-nav__link" href="#">Schedule</a>…
  </nav>
  <div class="st-header__scene" aria-hidden="true"></div>   <!-- background: var(--st-scene-image) -->
</header>
<div class="st-ticker" aria-label="Latest scores">          <!-- Scoreboard only -->
  <span class="st-ticker__tag">Final</span><span class="st-ticker__item">MUD 11 · SLG 14</span><span class="st-ticker__sep" aria-hidden="true">|</span>…
</div>
<footer class="st-footer">
  <div class="st-footer__scene" aria-hidden="true"></div>   <!-- background: var(--st-scene-image-footer) -->
  <div class="st-footer__body">
    <div class="st-footer__brand"><span class="st-brand__badge st-brand__badge--sm">…</span><span class="st-footer__name">…</span><span class="st-footer__meta">…</span></div>
    <nav class="st-footer__nav" aria-label="Footer"><a href="#">Teams</a>…</nav>
    <p class="st-footer__where">Thursday evenings · [Gym name]</p>
    <p class="st-footer__credit">Made with <a href="#">scorers-table</a></p>
  </div>
</footer>
```
Page title block (game and team pages): `.st-page-title` with `.st-back` (link), `__eyebrow`, `__title` (h1), `__sub`.
Sections: `.st-section` > `.st-section__head` (`__title` h2, `__aside` date or link) , content, `.st-note`.

### Scores

* **Result card** `a.st-result-card` (whole card is the link): `__team` (+ `is-winner`) = `.st-chip`,
  `__name`, `__score`; `__foot` = `__note` + `__link`. Variant `--lines`: the card holds a
  `.st-line-score--card` instead of two score rows (curling, slo-pitch). Variant `--tie`.
* **Final panel** `.st-final` (top of a game page): `__status`, `__team` ×2 (chip, name, record),
  `__score` (the two big numbers; the loser's is `is-dim`), then the full line score inside it
  or beside it, depending on layout.
* **Line score** `table.st-line-score.st-line-score--<quarters|ends|periods|innings>` with
  `--card` (compact, inside a result card) or `--full`. Head cells = period numbers; `__total`
  column; `__extra` columns (slo-pitch R/H are `__total` + `__extra`). Cell states:
  `is-won` (won the quarter/end: underline or bold), `is-mark` (stolen end, run-limit inning:
  tinted cell or circled number), `is-blank`, `is-void` (X, not played), `is-open` (open
  inning). Hammer marker: `svg.st-hammer` inside the team cell or the end cell. Legend:
  `.st-legend` of `__item`s.
* **Event log** (hockey scoring summary; penalties table reuses `.st-table`): `.st-events` >
  `__group` > `__head` (period + running total) + `.st-event` (grid: `__time`, `.st-chip`,
  `__who` with `__sub` for assists, `__score`); `.st-badge` for GWG.
* **Roster** (curling lineups): `.st-roster` > `__head` (chip, team name, link) + `__row`
  (`__role` label, `__name`; `.st-badge--outline` for Spare).
* **Stat tables on game pages** (box score, skaters, goalies, batting, game in numbers) are
  `.st-table` in `.st-table-wrap`, with `tfoot` totals.

### Data

* **Standings** `.st-table-wrap > table.st-table.st-table--standings`: first cell =
  `.st-rank` + `.st-chip` + name; key column cells have `is-key`; the note below is `.st-note`.
  **Race** (Scoreboard's standings): `.st-race` > `__row` (`--lead` for first) = `__rank`,
  `__name` + `__sub` (record), `__bar` > `__fill` (style `width:NN%`), `__points`.
* **Leader tile** `a.st-leader-tile`: `__label`, `__value`, `__name`, `__meta`; modifier
  `--hot` / `--accent` picks the top edge colour. Grid wrapper `.st-leader-grid` (2 columns).
* **Leader row** `.st-leader-list` > `__title` + `a.st-leader-row` = `__rank`, `__name`
  (+ `__team`), `__value`. Hockey's points leaders are a `.st-table` with `.st-rank-chip`
  (round, `is-first` gold); Scoreboard's are `.st-leader-board` rows (huge `__value`).
* **Game row** `.st-game-row` = `__surface` (Sheet A / Diamond 1 / Pad 2; optional icon),
  `__teams` (+ `__vs`), `__time` (+ `__sub`). CSS grid with named areas
  `surface teams time`, so a layout can reorder (Scoreboard puts time first).
* **Next-game panel** `.st-next-game`: `__label`, `__date`, `__where`, optional `__group-label`
  (curling groups draws by time), `__rows` of game rows, `__foot` (bye note, link), optional
  `__emblem` (curling house, hockey face-off circle: decoration, `aria-hidden`).
* **Team card** `a.st-team-card` (not mocked in round 1; from the Masters site's team card,
  restyled per layout, flagged for review): colour edge from `--st-team`, `__name`,
  `__record` (+ `__points`), `__rank`.
