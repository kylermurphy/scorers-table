# scorers-table

A public template for a small recreational league's website (standings,
schedule, results, player stats, past seasons), built from the league's paper
score sheets. Several sports: basketball (built, stage 5 part 1), then curling, hockey, slo-pitch. Read
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

## The core (stage 4, merged) and basketball (stage 5, in review as a pull request)
Read `docs/stage-4-spec.md` (the design, with the decisions the owner approved), `docs/data.md` (the data files)
and `docs/sports.md` (the sport folder) before touching it; for basketball also `docs/stage-5-basketball-spec.md`,
`sports/basketball/README.md` and `docs/open-questions.md` (the settings a league still has to decide).
```
league.yml                  the league's settings (the one file a setup person edits)
data/                       seasons.yml and one folder per season: teams.yml, players.yml, schedule.csv,
                            games/ (finished sheets), drafts/ (never built), sheets/ (photos)
sports/<id>/                a sport: sport.yml, rules.py (check, read, present, derive), sample.py, README.md, fixtures/
                            (shared test cases for the later JS port). `basketball` ships (`league.yml` says `sport: basketball`;
                            `convert_masters.py` there turns a Masters data folder into this layout); `stub` is the core's
                            test sport (`demo: false`)
scripts/core/               the Python package: model (types), problems, config, sports, loader, standings,
                            compute*, calendars, writer
scripts/build.py            load -> check -> compute -> write _data/computed/, stub pages, calendars
scripts/preview_root.py     the temporary root a sport preview is built from; scripts/build_preview.sh builds /preview/ and /<sport>/
_layouts/ _includes/        Jekyll: one include per design-system part (_includes/parts, _includes/shell)
index.html schedule/ ...    the pages; assets/css (stage 3), assets/js/site.js (theme toggle only)
tests/                      pytest: unit, golden (tests/golden), Jekyll smoke, parity with the design-system page
.github/workflows/build.yml tests -> contrast -> build -> Jekyll -> preview -> link check -> deploy
```
Commands: `python scripts/build.py [--sample] [--check]` (always run it before previewing data changes: it also
writes the stub pages and the active season), `bundle exec jekyll serve`, `python -m pytest`,
`python scripts/make_sample.py` (rewrites `data/sample-*/` for the sport in `league.yml`: made-up, deterministic,
committed), `bundle exec jekyll build && scripts/build_preview.sh` (the preview copies into `_site/`).
Rules that came with the core:
- **`_data/computed/`, `_games/`, `_players/`, `_teams/`, `_archive/`, `calendar/` are generated** (git-ignored):
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
- **Core parts stay sport-neutral**: `top_performer`, `stats.columns`, the leaderboard keys `zero`, `playoffs`,
  `home`, `player_rank` and rate ranking before rounding are core features that basketball needed; nothing tests
  a sport id.
- **Converted Masters data is never committed** (it names real players). Tests convert into a temporary folder;
  `tests/test_masters_parity.py` runs only with `MASTERS_SITE` set to a Masters checkout.
- Unset "league decides" settings build with the sport's typical default, show a visible `[placeholder]` and
  appear in the build's "Still to decide" list: never invent a league fact.

## Stack
Jekyll 4.4 on GitHub Pages, deployed by GitHub Actions after a Python step (PyYAML + standard library) that
checks the data and works out the numbers. No Ruby plugins beyond Pages-safe ones. No JavaScript framework:
`assets/js/site.js` is the theme toggle; the pages work with JavaScript off.
