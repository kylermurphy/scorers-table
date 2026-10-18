# scorers-table

A public template for a small recreational league's website (standings,
schedule, results, player stats, past seasons), built from the league's paper
score sheets. Several sports: basketball (built, stage 5 part 1, merged) and curling (built, stage 5 part 2, merged), then
hockey, slo-pitch. The repository's own site is a **showcase** (a landing page at `/` with a card and live
mini-preview per sport; built, in review as a pull request). Read
`BRIEF.md` (what it is and why), `PLAN.md` (the stages) and `docs/design.md` (the designs) before starting
work. Grew out of `tb-masters-basketball/website`; that repo is a reference,
not a dependency.

## Rules that hold everywhere
- **Data files are the source of truth.** Never hand-edit generated files.
- **The sport rules live in one place** (Python), with a JavaScript copy for the
  entry page; shared test files keep the two in step. Change the Python first.
- **Every problem names its box** (a path like `running.home.14`), so the entry
  page can point at it.
- **Never invent league facts.** Sport defaults are "typical club rules" from
  `BRIEF.md`; anything a league must decide shows as a visible `[placeholder]`
  and is listed for the league.
- **Sample data uses made-up leagues and names**, nothing that looks real.
- **Players are "First L."**, with an optional number. Never full names,
  contact details or photos.
- **No analytics, ads, trackers or cookie banners.**
- **Phones first:** every page works at 360 px with no sideways page scroll;
  wide tables scroll in their own box with the first column fixed. WCAG AA
  contrast in light and dark, 44 px touch targets, real `<button>`, `<a>` and
  `<table>` elements. Every page works with JavaScript off, except the entry
  page.
- **Colours only through CSS variables** from the layout's tokens; no raw hex in
  page CSS. **Paths through `relative_url`**, so a league can host it anywhere.
- **Reuse the shared parts** (result card, line score, standings table...);
  something new becomes a reusable part, not a one-off.
- Before calling a page done, screenshot it at 390 px in both themes (desktop
  at 1440 px once stage 9 starts).

## Design system (stage 3, merged)
CSS lives in `assets/css/` (`tokens.css`, `layouts/<id>.css`, `base.css`, `parts-*.css`, `fonts.css`,
`fallbacks.css`); read `docs/design.md` before touching it. Load order: `fonts, tokens, layouts/<layout>,
base, parts-shell, parts-scores, parts-data, fallbacks`. A page picks its look with
`<html data-layout="<id>" data-theme="light|dark">`; a league that sets its own colour also puts an inline
`--st-league-color` (and `--st-league-color-dark`) and the attribute `data-league-colour` on `<html>`, which
makes each layout re-derive its accents. **Parts CSS (`base.css`, `parts-*.css`) may only read `--st-*`
roles**, never raw colours or a layout's literals; colours are defined only in `layouts/<id>.css`.
`python scripts/build_design_system.py` rebuilds `docs/design-system/index.html` (generated, never
hand-edit; `--inline --out <file>` writes a single self-contained copy). `fallbacks.css` and
`docs/contrast.md` are generated too: never edit them by hand.
Checks to run after any CSS change: `python scripts/check_contrast.py` (WCAG AA for every pair in both
themes and every example league colour; rewrites `docs/contrast.md`; must pass) and `python -m pytest`
(`pip install pytest`). `python scripts/build_css_fallbacks.py` regenerates `fallbacks.css`.

## The core (stage 4, merged), basketball (stage 5 part 1, merged), curling (part 2, merged) and the landing page
Read `docs/stage-4-spec.md` (the design, with the decisions the owner approved), `docs/data.md` (the data files)
and `docs/sports.md` (the sport folder) before touching it; for basketball also `docs/stage-5-basketball-spec.md`,
`sports/basketball/README.md`, for curling `docs/stage-5-curling-spec.md` and `sports/curling/README.md`, and
`docs/open-questions.md` (the settings a league still has to decide); for the landing page
`docs/landing-page-plan.md` (the approved plan) and `docs/data.md`, "The front page".
```
league.yml                  the league's settings (the one file a setup person edits); `landing_page` sits beside
                            name, sport and timezone at the top
landing.yml                 the words of the landing page (title, intro, links, `coming_soon`); read only while
                            `landing_page: true`, excluded from the site
landing/index.html          the landing page's source (permalink `/`; excluded from every other build)
data/                       seasons.yml and one folder per season: teams.yml, players.yml, schedule.csv,
                            games/ (finished sheets), drafts/ (never built), sheets/ (photos)
sports/<id>/                a sport: sport.yml, rules.py (check, read, present, derive), sample.py, README.md, fixtures/
                            (shared test cases for the later JS port). `basketball` ships (`league.yml` says `sport: basketball`;
                            `convert_masters.py` there turns a Masters data folder into this layout); `curling` is built too
                            (a league switches with `sport: curling`); `stub` is the core's test sport (`demo: false`)
scripts/landing.py          the landing page's data (landing.json: each demo sport's top-3 standings and latest result, built
                            like `/<sport>/`), the `landing.yml`/`blurb` checks and the Jekyll overlay `_config.landing.yml`
scripts/core/               the Python package: model (types), problems, config, sports, loader, standings,
                            compute*, calendars, writer
scripts/build.py            load -> check -> compute -> write _data/computed/, stub pages, calendars
scripts/preview_root.py     the temporary root a sport preview is built from; scripts/build_preview.sh builds /preview/ (not while the landing page is on), /basketball/ and /curling/
_layouts/ _includes/        Jekyll: one include per design-system part (_includes/parts, _includes/shell; parts/sport-card.html
                            is the landing page's card, a window in the sport's own look)
index.html schedule/ ...    the pages; assets/css (stage 3), assets/js/site.js (the theme toggle, and its copy onto the landing page's windows)
tests/                      pytest: unit, golden (tests/golden), Jekyll smoke, parity with the design-system page
.github/workflows/build.yml tests -> contrast -> build -> Jekyll -> preview -> link check -> deploy
```
Commands: `python scripts/build.py [--sample] [--check]` (always run it before previewing data changes: it also
writes the stub pages and the active season), `bundle exec jekyll serve`, `python -m pytest`,
`python scripts/make_sample.py` (rewrites `data/sample-*/` for the sport in `league.yml`: made-up, deterministic,
committed), `bundle exec jekyll build && scripts/build_preview.sh` (the preview copies into `_site/`); with `landing_page: true`
the first build is `bundle exec jekyll build --config _config.yml,_config.landing.yml`.
Rules that came with the core:
- **`_data/computed/`, `_games/`, `_players/`, `_teams/`, `_archive/`, `calendar/` and `_config.landing.yml` are generated** (git-ignored):
  never edit them. The golden files in `tests/golden/` are regenerated with `UPDATE_GOLDEN=1 pytest tests/test_golden.py`
  and reviewed by eye.
- **Every problem names its box** (`file: path: message`); the build stops with all of them and writes nothing.
- **Includes never test the sport** and read only the computed JSON; sports supply data (words, flags, blocks),
  not templates. A new part is added to the design system first (specimen, CSS, contrast pairs) and then to
  `_includes/parts/` with a parity case.
- **Sport rules live in `sports/<id>/rules.py`** (Python first; the JavaScript copy for the entry page comes
  with stage 7 and is tested against the shared `sports/<id>/fixtures/`, so change a rule and rewrite the
  fixtures: `UPDATE_FIXTURES=1 python -m pytest tests/test_basketball_fixtures.py`, then read the diff).
- **Sport previews.** `league.yml` `sport_previews` (shipped `true`) builds a made-up demo league for every sport
  with a `sample.py` at `/<sport>/` (not the stub: `demo: false`), beside `preview` (`/preview/`, the league's own
  look with made-up games). Neither is linked from the league's own pages; sport previews are always `noindex`
  and have no calendar files. A new sport appears there by itself. Golden files are per sport
  (`tests/golden/<sport>/`, `test_golden.py`).
- **The landing page** (`landing_page` in `league.yml`; absent means `false`, the repository ships `true`). `true`: the root `/`
  is the scorers-table landing page (Basketball look) with one card per sport in `sport_previews` and a "Coming soon"
  card per `landing.yml` `coming_soon` entry; the league's own pages are left out of the root build by the overlay
  `_config.landing.yml` (written by every plain `build.py`; `landing_page: false` alone while off), so `/schedule/`
  and the other old root addresses do not exist, the sample league is at `/basketball/` only, `/preview/` is not
  built, and a demo's banner says "All sports". `true` with `sport_previews` off is an error. A real league sets
  `false`. Every plain build prints a note while it is on. The card numbers come from the same computation as each
  demo (`scripts/landing.py`); nothing is typed in. A sport gets a card by itself once it has a `sample.py` and a
  `blurb:` in `sport.yml` (one line, at most 100 characters; the contract test requires it); take it off
  `landing.yml` `coming_soon` then (the build warns). The window in a card is a nested layout: never write a
  `[data-layout=x] .st-y` rule for a class a window uses (`tests/test_nested_layout.py`). A page added to the root
  later must be added to `LEAGUE_PAGES` in `scripts/landing.py`. Don't link the design-system page from it.
  "Off means unchanged" is held by `tests/golden/landing/off-site.sha256` (the hash of every page built with the
  line left out, checked against the pre-landing commit a9c507f): a page change made on purpose rewrites it with
  `UPDATE_GOLDEN=1 python -m pytest tests/test_jekyll.py -k left_out_every_page` (read which pages its diff names).
- **Core parts stay sport-neutral**: `top_performer`, `stats.columns`, the leaderboard keys `zero`, `playoffs`,
  `home`, `player_rank` and rate ranking before rounding are core features that basketball needed; curling added
  the `numbers` and `roster` blocks, `words.extra` ("EE" for "OT"), `display.results_legend`, `display.team_sub`
  (the skip line on a team card), the card's own `line_score` and `meta_extra`, an empty player group
  (`stats.player: []`: games played only), the sample generator's `TIMES`, `SURFACES`, `NUMBERS`, `POSITIONS`
  and `NOTES`, and team boards that count only games with a score sheet (a forfeit is not a game there). Nothing
  tests a sport id. `docs/sports.md` lists every key.
- **Curling** (`sports/curling/`): the game file is a box-for-box copy of the score card (an end box per rink, the
  first-end hammer, optional extra ends, a concession or `time_called`, lineups with a spare's `spare_for`); the
  hammer of every later end, steals, blanks and big ends are worked out by `read`. `rules.ends` (4 to 10, default 8),
  `rules.extra_end` and the standings ties, forfeit and tiebreakers are `[placeholder]` until a league sets them.
  Never name a rink after the skip's surname. The shipped `league.yml` and the committed `data/sample-*` stay
  basketball (the curling sample is written by `make_sample.py` for the golden files and
  `/curling/`). Rewrite its fixtures after a rule change with
  `UPDATE_FIXTURES=1 python -m pytest tests/test_curling_fixtures.py`.
- **Converted Masters data is never committed** (it names real players). Tests convert into a temporary folder;
  `tests/test_masters_parity.py` runs only with `MASTERS_SITE` set to a Masters checkout.
- Unset "league decides" settings build with the sport's typical default, show a visible `[placeholder]` and
  appear in the build's "Still to decide" list: never invent a league fact.

## Stack
Jekyll 4.4 on GitHub Pages, deployed by GitHub Actions after a Python step (PyYAML + standard library) that
checks the data and works out the numbers. No Ruby plugins beyond Pages-safe ones. No JavaScript framework:
`assets/js/site.js` is the theme toggle (and copies the theme onto the landing page's windows); the pages work with JavaScript off.
