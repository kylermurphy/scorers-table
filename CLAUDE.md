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

## Stack (planned, stage 4)
Jekyll on GitHub Pages, built by GitHub Actions after a Python step that
checks the data and works out the numbers. No JavaScript framework.
