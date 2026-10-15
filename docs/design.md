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


## Parts by layout: what each part looks like

Written by the agents that built each part group, checked against the approved mockups. 'Roles' lists the
token roles the part reads; 'gaps' are places the contract had no exact role and the closest one was used.

### Shell parts


Parts: header, nav tabs, theme button, ticker, footer, page title block, section heading.
Anchors are selected as `.st-page .st-x` (beats base.css `.st-page a`), margins on h1/p likewise.
All colours come from roles; the only translucent colours are `color-mix(in oklab, ... transparent)`
(toggle hover, ticker separators). Focus rings inside header, nav, footer and ticker take the bar's own
text colour (`--st-header-text`, `--st-nav-text` in Classic, `--st-footer-link`) because `--st-focus` can vanish there.

#### Shared anatomy and classes
- `.st-header` > `.st-header__top` (flex: `a.st-brand` + `.st-theme-toggle`) + `nav.st-nav` + `.st-header__scene` (layout-owned).
  Top row and nav are `position: relative; z-index: 1`, so any scene sits behind them.
- `.st-brand__badge` is a text monogram in a circle (`role="img"` + aria-label in the header, `aria-hidden` in the footer).
  A league logo replaces it: `<span class="st-brand__badge"><img ...></span>` or `<img class="st-brand__badge">`; the
  monogram fill, ring and decoration are switched off when it holds an `<img>` (`:has(> img)`). Modifier `--sm` (footer, 36 px; 44 px in Basketball, 40 px in Slo-pitch).
- `.st-brand__tint` (added): the last word of the name, wrapped in every layout; only Scoreboard changes its colour.
- `.st-nav__link`, current = `aria-current="page"` (underline in `--st-tab`). Links are 44 px tall and at least 44 px wide.
  The nav scrolls inside itself (`overflow-x: auto`, no scrollbar) if it overflows, so the page never scrolls sideways.
- `.st-theme-toggle`: 44 px round `<button>`, one inline SVG. The header specimen shows the moon (label "Switch to dark theme") on the
  light frame and the sun ("Switch to light theme") on the dark frame, like the dark mockups. JS swaps SVG + label.
  With JavaScript off the button does nothing: stage 4 should hide it until site.js runs.
- `.st-ticker` (`role="region"` + `tabindex="0"` added so it is keyboard-scrollable): `__tag`, `__item` (+ `--quiet` for a bye), `__sep`.
- `.st-footer` > `.st-footer__scene` + `.st-footer__body` (the footer background is on the body, so a scene above it can show the page). Children:
  `__brand` (badge `--sm`, `__name`; `__meta` is styled but the sample does not use it), `__nav` (links), `__where`, `__credit`.
  The credit link is a 44 px target (negative block margin keeps the line height).
- `.st-page-title` (goes inside `.st-main`, which gives the gutters): `.st-back`, `__eyebrow` (optional), `__title` (h1), `__sub`
  (date line, `<br>` then venue line). Size, case and weight come from `--st-fs-title`, `--st-display-transform`, `--st-w-display`.
- Section heading: base.css owns the markup; the specimen shows a title + date aside, and a title + link aside + `.st-note`.

#### Per layout
##### Header
- **Basketball**: `header-bg` gradient (sunrise light, night sky dark) with the layout's court-and-hills scene at the bottom; name Barlow Condensed 23 px uppercase;
  meta uppercase 13 px `.12em` in `header-muted` behind an 18x3 px rule in `--st-tab`; badge white disc, 3 px `--st-tab` ring, text in `--st-league-color`;
  tabs Barlow Condensed uppercase 15 px, current tab white with a 3 px coral underline.
- **Curling**: flat ink `header-bg`, house rings (layout scene) behind the text, 4 px bottom border in `--st-header-line` (red); name Alegreya 800 23 px, no uppercase;
  meta plain 14 px; badge = the house (3 px `--st-link` ring, white, `--st-hot` ring, white, text in league colour); tabs Source Sans 16 px, current bold white with a 3 px white underline.
- **Hockey**: boards `header-bg`, name Saira Condensed 800 uppercase; meta uppercase behind an 18x3 gold rule (`--st-tab`); badge = white disc, `--st-hot` ring, a `--st-link` line across the lower half (`::after`),
  dark text; tabs Saira Condensed 16 px uppercase, gold 3 px underline on the current tab. The 6 px gold bar and rink lines under the nav are the layout's scene.
- **Slo-pitch**: green `header-bg`, name Zilla Slab 700 23 px (no uppercase); meta uppercase 13 px `.1em`; badge = white disc with a thin league-colour ring, slab monogram;
  tabs Work Sans 15 px (500, current 600), cream (`--st-tab`) 3 px underline; clay arc scene under the nav.
- **Classic**: WHITE header bar (`header-bg`; name, meta, toggle in `header-text`/`header-muted`, a 1 px `--st-header-line` under it), badge 48 px in `--st-league-base` with a white inner ring;
  then a SEPARATE bar in `--st-nav-bg` (league colour) with `--st-nav-text` / `--st-nav-muted` tabs and a 3 px `--st-tab` (white) underline.
  Name Barlow Condensed 22 px uppercase, meta uppercase muted `.08em`. No scene.
- **Scoreboard**: flat league-colour bar, name Anton 25 px uppercase with its last word tinted (`header-text` mixed 22% toward the league colour), meta Chakra Petch 12 px uppercase `.12em`;
  white 46 px badge, toggle with a 2 px ring; tabs Chakra Petch 13 px uppercase, 4 px `--st-tab` (amber) underline; the nav scrolls inside itself.

##### Nav tabs
Same as the header tabs above; the specimen wraps them in a `.st-header` with Stats as the current tab.

##### Theme button
Header-coloured strip showing both states. 1 px `--st-header-button-line` ring (Scoreboard 2 px, Classic none: the icon is in the league colour on white).

##### Ticker (Scoreboard only)
Strip in `--st-footer-bg`, items `--st-footer-link`, uppercase Chakra Petch 13 px `.06em`; tag ("Final") in `--st-score-text` (amber), separators `|` and the "bye" item in `--st-footer-muted`.
Scrolls inside itself when the scores do not fit.

##### Footer
- **Basketball**: hills scene above a `footer-bg` body; 44 px badge with coral ring, name Barlow Condensed 19 px uppercase; links 44 px; where line, credit with no divider.
- **Curling**: flat ink body, house badge (small), name Alegreya 18 px; the where line ("Tuesday Mixed league") sits right under the name (`order`); links; 1 px `--st-footer-line` rule above the credit.
- **Hockey**: 6 px `--st-footer-accent` (gold) strip on top of the boards body, small badge, name Saira Condensed uppercase; where line and credit without divider.
- **Slo-pitch**: dark scorebook-ink body, 40 px badge, slab name 20 px, links, divider above the credit.
- **Classic**: ink-navy body, no badge, name Barlow Condensed 17 px uppercase with the where line right under it, links, divider above the credit.
- **Scoreboard**: black body, no badge, name Anton 22 px uppercase, links 14 px, divider above the credit.

##### Page title block
Back link in `--st-link` (Curling: 16 px bold), eyebrow uppercase 13 px `--st-muted`, h1 in the display face (Basketball/Hockey 32 px uppercase; Curling Alegreya 29 px; Slo-pitch slab 30 px; Classic/Scoreboard uppercase 32 px), date line `--st-muted` 15 px.

##### Section heading
Base look (display face, `--st-fs-h2`, aside in `--st-muted` or a `--st-link` link). Hockey adds three rink-line bars before the title (`--st-link`, `--st-hot`, `--st-link`, a gradient on `::before`). Scoreboard's titles are Anton from the layout tokens.

#### Gaps and deviations
- No ticker roles: uses footer-bg/footer-link/footer-muted/score-text as agreed with the lead. The mockup tag was a pink league tint; it is amber now.
- Badge colours have no roles: monogram text uses `--st-league-color` (the light input, so it is AA on the white disc in both themes); rings use `--st-tab`, `--st-link`, `--st-hot`, `--st-league-base`.
- Mockup logos (curling house, hockey rink, slo-pitch seams) are approximated with rings (box-shadow) around a text monogram; the clay dashes on the slo-pitch badge are left out.
- Footer where line: always `__where`; Curling and Classic move it under the name with `order` instead of a separate `__meta` markup.
- Nav links and footer links get `min-width/min-height: 44px`, so the gaps between short links are slightly wider than the mockups; mockup nav links were 40-42 px tall.
- The generator's `docs/design-system/ds.css` has `.ds h1/.ds h2/.ds h3` rules that leak into every specimen frame (a 2 px rule and 48 px margin above each `h2.st-section__title`, margin on the h1). Scope them to `.ds-wrap > h2` etc. (I previewed with that change).
- Remaining tap-target misses in the frames are not shell parts: `.st-race__row` (Scoreboard standings rows) and a "Full standings" link in the race part. Every shell link and button is at least 44 x 44 px at 360 and 390 px; the shell parts cause no sideways page scroll (only the ticker scrolls inside itself).

### Score parts


Files: `assets/css/parts-scores.css`, `scripts/design_system/specimens_scores.py`.
Specimen parts (Scores group, in order): result-card (sports=all), result-card-hero (Scoreboard only, all four sports),
final-panel (all), line-score (all), event-log (hockey, every layout), roster (curling, every layout),
game-tables (layout's own sports).

#### Anatomy additions (class names added to the contract)

* **Result card**: `a.st-card.st-result-card` (reuses base `.st-card`), `__head` (slo-pitch eyebrow "Final · Diamond 1"),
  `__team` (+`is-winner`) > `.st-chip`, `__name`, `__score`; `__foot` > `__note`, `__link` (chevron is `span.st-chevron`,
  hidden in Classic). Variants `--lines`, `--tie`, `--hero`.
  Hero (`div.st-result-card.st-result-card--hero`, not a link; the Box score `a.st-button` is the target):
  `__eyebrow`, `st-final__head st-final__head--board` (reused), `__periods` > `li.st-period-tile` (`__label`, `__pair` with
  `.is-lead`/`.is-dim`) for quarters and periods, or a `--card` line score for ends and innings, `__top`.
* **Final panel**: `section.st-final` > `__head` (`__status`, `__sub`, `__team`×2 [`is-winner`] = `__name` + `__record`,
  `__score` = `__num`(`is-first`/`is-second`, `is-dim` on the loser) + `__sep`) and `__body` (`__titlerow` = `__title` + `__meta`,
  `.st-line-scroll`, `__foot` [`--split`], `__note`). One markup, every layout; layouts reshape it (below).
* **Line score**: `.st-line-scroll` (scroll box; `role=region aria-label tabindex=0` except inside a link),
  `table.st-line-score--<shape> --<card|full>`, `__team` (sticky first column, chip + `__name`), `__total`, `__extra`, `__open`
  (the word "open" under an inning number), `__n` (wrapper of a marked number so a layout can circle it); row classes
  `is-winner`/`is-loser`; cell classes `is-won is-mark is-blank is-void is-open`; `svg.st-hammer` (`__ring/__mid/__core`);
  `.st-legend` > `__item` > `__key--won|mark|blank|limit|x|text`; `.st-legend--stack`.
* **Event log**: `.st-events` > `__group` > `h3.__head` (`<span>` period + `__tally`) + `ol.__list` > `li.st-event`
  (`__time`, chip with role=img + aria-label, `__who` > `__name`, `__sub`, `__score`); GWG = `.st-badge`.
  Penalties = `.st-table.st-table--events` with `.st-table__strong`, chip + hidden team name in the player cell, `.st-legend` of chips.
* **Roster**: `.st-roster` > `a.__head` (chip, `__team`, `__link`) + `ol.__list` > `li.__row` (`__role`, `__name` [`is-key` = skip, bold],
  Spare = `.st-badge.st-badge--outline` + `__for`).
* **Game-page tables**: `.st-table--box` (number column + player column both sticky, used by box score and batting order),
  `.st-table--numbers` (the game in numbers), `.st-table--events`; cell helpers `.st-table__strong`, `.st-table__big`,
  `.is-hot` (stolen end text), `.is-key`, `a.st-player` (44 px target without changing row height), `tfoot` totals (rule added here,
  not in base.css); `.st-team-heading` (+`--sm`) = chip + `__name` + `__score`; `.st-game-block`; `.st-facts` > `__row` >
  `__label` + `__value` (+`__team`); `.st-top-scorer` (`__main`, `__label`, `__name`, `__detail`, `__value`, `__num`, `__unit`;
  the name link stretches over the whole tile); `.st-note--intro`.
* Local helper properties (aliases of roles, never new colours): `--ls-text --ls-muted --ls-line --ls-rule --ls-bg --ls-pad-x`
  (line score and panel foot follow their context), `--hm-ring --hm-mid --hm-core` (hammer), `--fp-text --fp-muted` (panel head).

#### Result card, per layout
* **Basketball**: white card, 10 px radius, two rows (chip, name, 24 px condensed score; winner bold ink, loser muted), a hairline, then
  "Top: **#23 Dave M.** 24 pts" left and "Box score ›" in the league blue right. `--lines` puts the quarter table under the rows.
* **Curling**: `--lines` card: the end-by-end table (names with the hammer marker after the team that had it in end 1, scored ends bold,
  stolen ends in the pale red tint, X for unplayed ends, big serif Tot), hairline, "Sheet A · 6:30 PM" and "Game ›". A legend row sits above the list.
* **Hockey**: 14 px radius, two rows with 28 px heavy condensed scores, foot "Final · GWG **#12 Gord P.**" and "Game sheet ›"; a tie has both rows in ink
  ("Final · **Tie**, 1 point each").
* **Slo-pitch**: `--lines` card with an uppercase eyebrow ("Final · Tie · Diamond 3") over a ruled scorebook table, 5-run innings underlined in clay,
  R bold (winner green, loser muted), H plain; foot "Top bat: **Gary T.** 3 for 4" and "Box score ›" in green.
* **Classic**: the same rows, but the foot is a single quiet line in the league colour, bold: "Final · Sheet A · Game" (time dropped, chevron hidden,
  separator dots drawn with `::after`); curling `--lines` use the plain tinted stolen end.
* **Scoreboard**: 2 px ink outline (`--st-line-strong`, `--st-border-strong`), no chips, Chakra Petch names and digits, uppercase "BOX SCORE ›";
  the `--lines` form is digit tiles. **Hero** (`--hero`): black panel, "GAME OF THE WEEK" and "Final · Dec 3" in grey caps, display-font names,
  the score as two bordered digit tiles (winner amber, loser grey), then per-quarter tiles ("18 15", first number amber) for basketball, per-period tiles
  for hockey, a tile line score with the team codes for curling and slo-pitch (limit innings boxed in amber), the top performer sentence, a full-width red
  BOX SCORE button. Shown for all four sports (curling/hockey take their first result: no `featured` in the data).

#### Final panel, per layout
* **Basketball**: league-blue panel (12 px radius, 16 px padding). Row 1: FINAL (caps, muted) and "Rapids by 7". Row 2: chip + condensed uppercase name, record
  under it; the score 56 px condensed ("71 – 64", loser muted, dash small); right team mirrored (chip after the name). Inside, a lighter inset box (9% of the panel
  text colour over the panel) holds the quarter table; underlined highlight quarters in the coral `won-line`; legend below on the blue.
* **Curling**: a card whose top is an ink (navy) band holding the two names (bold body face, chip with a white ring) and the 48 px serif score; below it on the
  card surface "End by end" + "8 ends · no extra end", the end table (BP/HH codes, hammer markers in cells, blank end 1 shaded, Tot fenced by a heavy rule and
  a pale fill), then a hairline, the hammer sentence and the legend.
* **Hockey**: the rink: 3 px boards-coloured border, 30 px corners, blue lines at 28% and 72% and a red centre line drawn behind (`::before`, 24-30% mixes of
  `link` and `hot`). A black "FINAL" pill on top, centred chip/name/record columns, 72 px score; under a 2 px boards rule the period table with the dark T column
  (loser dimmed) and the foot "Goalies: **#31 Len T.** · **#1 Murray B.**" / "PIM 4–4".
* **Slo-pitch**: a two-row scorebook card (chip, 19-22 px name, record under it; the score 46 px slab at the right, winner in `accent` green, loser muted; WIN badge
  next to the winner). The line score is not inside it: "Line score" (h2) and its own ruled card follow, then the circled-5 and X notes as a stacked legend. A status
  ("Final") for other sports appears as a footer row of the score card.
* **Classic**: like Basketball with the league-colour panel (white underline for highlighted periods, `won-line` is white here).
* **Scoreboard**: black (`panel-bg`) panel: label row (GAME OF THE WEEK style: FINAL / sub), display-font names, two digit tiles, the line score as tiles, notes under a hairline.
  The same board look is `.st-final__head--board`, used by the hero.

#### Line score, per layout and shape
The four shapes are structure + cell rules in base; the layout supplies a skin that works for every shape.
* Quarters / periods: numbers; `is-won` underlines in `won-line` (only the basketball sample has data for it). Ends: zeros muted, scored ends in ink (`is-won`),
  `is-mark` = stolen end tint, `is-blank` column shade, `is-void` X, hammer svg in the cell (full) or after the name (card, end 1). Innings: numbers, `is-mark` = limit
  inning, `is-void` X, header "7 / OPEN" (`is-open`); R `__total`, H `__extra`.
* **Basketball / Classic skin**: hairline rows, 2 px rule under the head in `rule`; total bigger and bold, no decoration. Marked cells are tinted rounded boxes
  (`mark-bg` / `mark-text`). In the panel the colours switch to panel roles. Curling in Basketball = the Curling mockup recoloured by tokens; slo-pitch innings = tinted limit cells.
* **Curling skin**: as above with the Tot column fenced by a 2 px `score-line` rule and a `surface-2` fill (full only).
* **Hockey skin**: the total column is a dark `score-bg` block with `score-text`, loser `score-dim`, in every shape and both sizes, so the ends table "keeps rink styling";
  bigger condensed numerals (28 px) for periods/quarters; stolen end and limit innings keep the gold tint.
* **Slo-pitch skin (scorebook)**: every cell boxed by a 1 px `score-line` grid (header cells on `surface-2`, total and H boxes tinted); full: limit innings circled (2 px `mark-line`
  ring), the chip is dropped to fit 390 px; card: grid lighter, limit inning underlined 2 px, no fills. Quarters, periods and ends get the ruled grid too; a stolen end is circled.
* **Scoreboard skin (digit tiles)**: each number on its own `score-bg` tile (2 px gaps), amber `score-text`; ends: zeros `score-dim`, scored ends amber; limit/stolen = 2 px `mark-line`
  outline box; blank = lighter tile; total in `panel-text`; loser total `score-dim`; hammer drawn in amber; team names small caps-ish text, no chips.
* **Legend keys follow the cells**: limit key = tinted square (default), ring (slo-pitch), outlined tile (scoreboard); stolen/blank keys use the same fills.
* Small phones: card tables let the team name wrap so the total never scrolls out of view; full tables scroll inside their box with the first column fixed.

#### Event log
* Basketball/Classic/Curling/Slo-pitch (default card): bordered card, group bands on `surface-2` with period and tally ("BLA 2 · WOL 1") in the display face, rows with time, chip, bold
  scorer + grey assists line, running score right; GWG is a `.st-badge`. Penalties: `.st-table` with PER/TIME/PLAYER/INFRACTION/MIN, chip + name, a legend of team chips below.
* **Hockey**: as the mockup: boards-blue table rule (token `rule`), gold GWG badge (`badge-bg`), "|||" heading marks come from the shell part.
* **Scoreboard**: 2 px ink outline, black group bands in `panel-bg` / `panel-text`, chips kept (they are the only team cue in a log).

#### Roster
Card with a `surface-2` head (chip, team name in the display face, "Rink ›" in the link colour; whole head is the link, 48 px), then rows: uppercase role label, name, skip bold, Spare outline badge and
"for Brian S.". Curling: as the mockup (serif team name). Basketball/Classic: uppercase condensed team name. Hockey: rounder card. Slo-pitch: slab name. Scoreboard: 2 px outline, black head,
amber link, no chips.

#### Game-page tables
Same `.st-table` in every layout; the layout comes through `rule` (head rule), `line`, fonts, and: slo-pitch totals row on `surface-2` with a heavy ink rule; Hockey table heads in the display face;
Scoreboard 2 px outline on `.st-table-wrap`. Box score: # column right-aligned and muted, player bold link, PTS `is-key`, tfoot "Team · 8 played". Numbers table: team codes with chips as column heads,
emphasis bold, stolen ends `is-hot`. Skaters/goalies: players as "#12 Gord P." links, goalie GA in 20 px display face. Batting: # + batter fixed, totals row.

#### Deliberate deviations
* The 3 px hockey boards and 30 px radius are literals (no token). Hammer marker rings use `link` (outer) and `hot` (core) instead of two literal blues/reds.
* Hero shown for curling/hockey with their first result (the mockups only draw basketball and slo-pitch).
* Curling Home cards in the mockup have no rule under the head: the card size uses a 1 px `line` rule instead of the 2 px `rule`.
* Scoreboard hides chips in cards, hero, roster and line scores (as the mockups) but keeps them in the event log and penalty table.
* The slo-pitch final line score keeps an opaque team column (white) over the ruled paper lines so the fixed column stays readable when scrolled.

#### Token-contract gaps (closest role used)
* No `radius-rink` / boards role: hockey boards = `score-bg`, rink lines = `link` (blue) and `hot` (red).
* No translucent panel-row solid: tint boxes inside panels are `color-mix(panel-text 9%, panel-bg)` because sticky cells need an opaque fill (`panel-row` is translucent and layouts differ).
* No "total cell" fill role: curling uses `surface-2` + `score-line`, hockey `score-bg`, slo-pitch `surface-2`, scoreboard `panel-text` on `score-bg`.
* No "blank end" text role: header text on a blank column uses `text`. No separate "hammer" colours (see above).
* `--st-focus` is replaced by `panel-text` in the final panel and the hero (as the lead asked).

#### Things for the lead
* **base.css reset beats bare-class margins**: `.st-page :is(h1,…,p)` (0,1,1) overrides `.st-note`, `.st-section__title` etc. (0,1,0), so `.st-note` has no top margin (the mockups have 8 px).
  I prefixed my own margins with `.st-page`; base `.st-note`/`.st-label` need the same.
* **Curling sample slots vs palette**: sample puts Button Pushers on slot 1, but curling.css slot 1 is grey (Stone Cold in standings order) so BP renders grey, the mockups red (same idea for Hockey/Classic: check).
* `scripts/design_system/specimens_scores.py` uses `team["code"]` only where `code_in_mockup` is true (curling full line score, hero tiles).
* Hero and final head use `!important` on two margins (`.st-final__status/__sub`) to beat the page reset.
* **`won-line` pairs in check_contrast.py**: I draw `won-line` only on (a) the coloured panel (Basketball/Classic, `panel-bg` tint), (b) `surface` (all layouts except Classic and Scoreboard)
  and (c) Scoreboard's black digit tiles. The current failures (`classic won-line/surface` white on white, `scoreboard won-line/surface` amber on white, `curling|hockey won-line/score-bg`) are pairs
  I never draw, except Classic off its panel, where my CSS underlines with `accent` instead (`--ls-won`). Suggest the checker pairs `won-line` with `panel-bg` (Basketball, Classic),
  `surface` (Curling, Hockey, Slo-pitch, Basketball) and `score-bg` (Scoreboard) only.

### Data parts


Files: `assets/css/parts-data.css`, `scripts/design_system/specimens_data.py` (Part ids `standings`,
`standings-table` (Scoreboard only), `leader-tile`, `leader-list`, `game-row`, `next-game`, `team-card`).
Checked at 360 and 390 px, light and dark, in all six layouts: no sideways page scroll, every link in a part is at
least 44 x 44 px, scroll boxes have role=region, aria-label, tabindex=0. No raw colours; no new roles.

Shared conventions
* Links in parts use `.st-page a.st-x` selectors so they beat `.st-page a`. Margins on `p`/`h*` use a `.st-page`
  prefix because base.css zeroes them with `.st-page :is(h1, h2, p, ...)`.
* Local variables, not roles: `--ng-*` (next-game panel colours), `--row-*` (game row colours), `--tile-edge` /
  `--tile-ink` (leader tile). Defaults come from roles; a layout or context repoints them.
* Team cell of a table is `<th scope="row">`; the head styling base.css gives every `th` is undone for it.

#### 1. Standings (`st-table--standings`, `st-race`)

Classes added: `.st-table-wrap--standings`, `.st-rank`, `.st-table__team`, `.st-race` (`<ol>`), `__row` (`<a>`)
`--lead`, `__rank`, `__who`, `__name`, `__sub`, `__bar`, `__fill`, `__points`. Roles: surface, line, rule, muted, text,
is-key bold; race: surface-2, text, muted, panel-bg/-text/-muted (lead row), score-text (lead rank), bar-track,
bar-fill, bar-lead.

One part, two renders: `render_standings` branches on `ctx.layout` (Scoreboard gets the race, everything else the
table). Reason: the generator's League-colour section picks `standings` by id for every layout, so a Scoreboard frame
there must show the race too. The Scoreboard's full table (the page the race links to) is the extra part
`standings-table` (`layouts=("scoreboard",)`).

* Basketball: rounded white card with a blue 2 px rule under the heads; rank number (muted), small team chip, bold
  team name; no bold key column (the data has none). Note under it.
* Curling: same card on the ice page, serif section title; PTS column bold; "Rink" heads the first column.
* Hockey: same card, blue rule, three-bar title mark from the shell; PTS bold; "Team".
* Slo-pitch: same card on scorebook paper, green accents come from tokens; PTS bold.
* Classic: no card; the table runs edge to edge between two hairlines (negative margin of one gutter, first/last
  cell padded by the gutter), navy rule under the heads, PTS bold.
* Scoreboard: "The race": a black row for the leader (amber rank in Anton, amber bar on a dim track, points at
  the right), grey rows for the rest (ink bar on a light track); basketball shows W-L at the right and
  `+61 · 1 GB` beside the name, the others show points and the record. Note: "Bar = win %. ..." with a bold link to
  the full standings. The full table (`standings-table`) is the usual table with display-face ranks.

Deviations: Scoreboard's dark lead row has a thin amber outline in the dark mockup; not drawn (no role for it).
Team names are plain text, not links (stage 4 can wrap them).

#### 2. Leaders (`st-leader-tile`, `st-leader-list`, `st-leader-board`)

Classes added: `.st-leader-group` (small label above a grid, e.g. Goalies), `.st-leader-lists`, `.st-leader-list__title`,
`.st-leader-row__who/__unit`, `.st-rank-chip` (`is-first`), `.st-leader-cell` (`__who/__name/__sub`, the link in
hockey's table cell), `.st-table--leaders`, `.st-leader-board` (`__title`, `__rows`, `__row` `--first`, `__value`,
`__who`, `__name`, `__sub`, `__pill`, `__digits`), `.st-leader-more`. Roles: hot, accent, surface, surface-2, line, muted,
rank-bg/-text, rank-1-bg/-text, panel-bg/-text/-muted (pill), score-bg/-text/-line (digits), line-strong.

Which items show follows the sample's `only_layouts`. A tile with no `edge` gets one by position (first `hot`, then
`accent`). A list marked `first_row_in_tile` skips rank 1 outside the Scoreboard (the tile shows it). In the Scoreboard
lists show three rows; a one-row list becomes a pill. Classic keeps the list's title visually hidden because the
section heading is the title. In the page the list comes before the tiles in Classic and hockey, after them in the
other sport layouts (the part specimens are separate: stage 4 orders them).

Tiles:
* Basketball: white card, 4 px coral (`hot`) or blue (`accent`) top edge, 40 px blue number.
* Curling: no edge; the number is red (`hot`) or blue (`accent`).
* Hockey: rounder card (14 px radius), blue or red top edge, number in ink; goalies under a "Goalies" label.
* Slo-pitch: clay edge and green edge, big green number, paper card.
* Classic: every tile gets a 4 px edge in the accent (the league colour); number in the accent.
* Scoreboard: 2 px outlined card (`line-strong`), fat 8 px top edge (`hot` = league colour, or ink), number in Anton.

Lists and tables:
* Basketball / slo-pitch / curling: card of rows: muted rank number, bold name with the team beside it in small
  grey (curling: just the name), value in accent at the right.
* Hockey: points as a `.st-table` (Player, G, A, PTS) with round rank chips (gold for 1st), name over team + GP,
  PTS in the display face; the link fills the cell (52 px row).
* Classic: rows with a round rank chip (navy for 1st), name over a grey second line (`7 GP · skip Gail R.`,
  `Blades · 8 GP · 11 G, 7 A`), big value with `steals` / `PTS` under it.
* Scoreboard: ranked boards, no card: arena number at the left (40 px for the first row, 32 px after), name bold
  with team under it, first row closed by a 2 px rule; the one-row list is a black pill with amber digits in a
  black box; a full-width outlined "All player stats" button closes the section.

Deviation: Classic-Curling's tiles have no edge in the mockup, Classic-Hockey's do; the layout takes the hockey look.

#### 3. Game row (`st-game-row`)

Classes added: `__surface` + `--tile | --label | --icon | --tag`, `__teams`, `__vs`, `__time`, `__sub`; modifiers
`--no-surface`, `--no-time`; list on the page `.st-game-rows--list`. Grid areas `surface teams time`. Roles: text, muted,
score-bg/-text (tile on the page), panel-row/-tile-bg/-tile-text (tile on a panel), line, surface, surface-2.
Specimen decides the surface by layout and sport; times drop " PM" where the mockup's foot says "All times PM".

* Basketball: no surface; teams left, bold time right; translucent white row on the blue panel, plain row with a
  hairline on the page.
* Curling: white letter tile (A, B, C) before the teams; no time on a panel row (the time is a group label above);
  in the page list the tile is navy and the time is shown.
* Hockey: teams left; time bold with "Pad 1" under it, at the right; 10 px row radius.
* Slo-pitch: outline diamond icon + "Diamond 1" in two small lines, teams, bold time at the right.
* Classic: "SHEET A" in small display capitals before the teams; time at the right without PM (curling).
* Scoreboard: time first, then a black "D1" tag with amber text, then teams (bold, "vs" in grey), grey rows; the
  page list is a 2 px outlined box.

Deviation: the slo-pitch Scoreboard mockup puts the tag first; the brief says time first, so the tag follows the time.

#### 4. Next-game panel (`st-next-game`)

Classes added: `--house`, `--faceoff` (emblem), `--demo` (rows only, used by the game-row specimen), `__head`, `__body`,
`__emblem` (`--house`, `--faceoff`, svg drawn with CSS classes `r1..r4`, `ring`, `dot`, `ticks`), `__where`. Roles:
panel-bg/-text/-muted/-label/-row/-tile-*, link and hot (house rings), hot (face-off), surface, surface-2, line-strong,
score-text, score-bg, panel-bg (Scoreboard title bar). Focus outlines inside use `--st-panel-text`.

* Basketball: royal-blue filled panel, small caps label, 28 px display date, two translucent rows, bye note and
  "Score sheets (PDF) ›" link at the foot.
* Curling: navy panel with the house-rings emblem (blue, white, red, white) top right; draws grouped under
  "6:30 PM" / "8:45 PM" labels; rows with the letter tile; the foot says "Sheet D: no league game."
* Hockey: near-black panel, gold label, a red face-off circle with tick marks cropped at the top right corner
  (55% opacity); rows with time and "Pad 1".
* Slo-pitch: green panel, rows with diamond icon and time.
* Classic: navy filled panel (the league colour via panel-bg), "SHEET A" labels and short times, "All times PM." foot.
* Scoreboard: outlined box (2 px `line-strong`), black title bar with "NEXT UP" in Anton and the date in amber at the
  right, then the venue, grey rows (time, tag, teams) and the foot (`Bye: Herons` or the all-times note).

Deviations: Basketball-Scoreboard's mockup rows are plain lines, slo-pitch's are grey boxes; grey boxes everywhere.
Slo-pitch Scoreboard's mockup has no black title bar (venue top right); the bar is used for both. In the dark theme
the Scoreboard's `panel-bg` equals `surface`, so the bar is only separated by its position.

#### 5. Team card (`st-team-card`): NOT MOCKED: PLEASE REVIEW

Markup: `a.st-team-card.st-team--N` > `__name`, `__record` (+ `__points`), optional `__sub` (curling: "Skip Gail R."),
`__rank` ("No. 3 in the standings", the Masters wording). Roles: surface, line, line-strong, team, accent, text, muted,
score-bg/-text/-line (Scoreboard).

* Basketball: white card with a 4 px team-colour top edge, condensed uppercase name, 40 px blue record with points.
* Curling: team colour as a 6 px band down the left side, serif name (no uppercase), record, skip line.
* Hockey: top edge, 14 px radius, condensed uppercase name.
* Slo-pitch: top edge, slab-serif name, a dotted scorebook rule above the rank line.
* Classic: as basketball (white card, top edge, league-blue record).
* Scoreboard: 2 px outlined card, 8 px team-colour top edge, Anton name, the record in lit amber digits on black.

#### Token-contract gaps

* `--st-panel-label` is grey in the Scoreboard, but the mockup's title-bar date and lead rank are amber: both use
  `--st-score-text`. A role such as `panel-accent` would be cleaner.
* No emblem roles: the house rings use `link` (blue), `panel-text` (white), `hot` (red); the face-off circle uses `hot`.
  Works in all themes now, but depends on `hot` staying the red line colour in hockey and curling.
* No role for the Scoreboard dark lead row's amber outline (not drawn).
* Rank-1 chip in Classic dark is a light circle (`rank-1-bg`), OK but unlike the mockup's dark one.

#### Things for the lead

* `docs/design-system/ds.css` styles `.ds h2/.ds h3/.ds h4` (rule above, big margins); every specimen with real
  headings gets a stray black line. Scope those selectors to `.ds-wrap > h2` etc. (I previewed with such a patched copy).
* Hockey section-title bars and the `st-section` skin are the shell's, not mine.
