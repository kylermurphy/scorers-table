# scorers-table

A public template for a small recreational league's website (standings,
schedule, results, player stats, past seasons), built from the league's paper
score sheets. Several sports: basketball, curling, hockey, slo-pitch. Read
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

## Design system (stage 3, delivered in a pull request awaiting review)
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

## Stack (planned, stage 4)
Jekyll on GitHub Pages, built by GitHub Actions after a Python step that
checks the data and works out the numbers. No JavaScript framework.
