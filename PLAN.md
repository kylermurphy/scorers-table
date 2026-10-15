# scorers-table: plan

Built in stages. Each stage ends with something to review (a design canvas or
a pull request), and the next stage starts only once it's approved. Each
stage says which Claude model fits it:

- **Opus**: judgement. Architecture, design direction, sport rules, reviews.
- **Sonnet**: building from a clear spec. Most code, tests, docs.
- **Haiku**: cheap, repeatable checks. Screenshot sweeps, link checks, lists.

A stage can run unattended (overnight) once its spec is approved: it ends in a
pull request, never a merge.

Status: stages 0-2 done (October 2026). Stage 3 (design system) is in review as a pull request; stage 4 starts once it is approved.

## Stage 0: brief and plan (done in the Masters website session)
- `BRIEF.md` (what it is, the core, the sports and their club rules, layouts,
  what carries over), this plan, a first `CLAUDE.md`.
- **Model:** Opus. **Review:** you read the brief, especially the club rules.

## Stage 1: phone mockups (done)
A design canvas with the six layouts on a phone (390 px), light and a dark
Home per layout (see `docs/design.md`):
- each sport layout: Home and Game (the line score is where sports differ most);
- Classic and Scoreboard: Home, each shown with two different sports, to prove
  they are general;
- one shared Stats screen per layout where it differs.

Builds on the Masters canvas (Recommended, Classic Club, Scoreboard).
- **Model:** Opus. **Review:** you pick, comment, iterate on the canvas.

## Stage 2: create the repo, first commit
`kylermurphy/scorers-table`, public. Mark it as a template repository
(Settings → General) once stage 8 makes it usable as one. The first commit:
`BRIEF.md`, `PLAN.md`, `CLAUDE.md`, a `README.md` stub, the licence,
`docs/design.md` (links to the design canvases) and `docs/dark-palettes.md`.
- **Model:** any (mechanical).

## Stage 3: design system
Turn the approved mockups into tokens and components: colour variables per
layout (light and dark), type scale, spacing, the shared parts (result card,
line score, standings table, leader row, game row, team card, next game panel).
A `docs/design.md` and the CSS variables.
- **Model:** Sonnet, with an Opus look at the result.

## Stage 4: the core
The sport-neutral skeleton, with no sport yet beyond a stub:
- data model: `data/seasons.yml`, per season `teams.yml`, `players.yml`,
  `schedule.csv`, `games/`, `drafts/`;
- `league.yml`: name, sport, layout, colours, logo, standings rule,
  tiebreakers, search engines, contact;
- the build script: load, check (problems with paths), standings engine with a
  pluggable points rule, calendars, stub pages, the active season and sample
  switch;
- Jekyll layouts and the shared parts; CI (tests, build, link check, deploy to
  Pages).
- **Model:** Opus designs the sport-folder interface (a short spec reviewed
  first); Sonnet builds it.

## Stage 5: one sport at a time, one PR each
Basketball first (ported from the Masters site, so it can be checked against a
real league), then curling, hockey, slo-pitch. Each PR adds the sport folder:
game file format and docs, rules in Python and JavaScript with shared test
files, stats, the line score and game page, a sample season generator, and
the sport's default standings rule.
- **Model:** Sonnet builds; Opus reviews each PR for rule mistakes.

## Stage 6: the six layouts as a setting
`layout:` in `league.yml` picks one of the six; the league's colours and logo
go on top. Every layout checked at 360 and 390 px in light and dark, for each
sport's sample season.
- **Model:** Sonnet builds; Haiku runs the screenshot sweeps and lists
  problems.

## Stage 7: the entry page for each sport
The sheet as boxes, checking as you type, paste from a chat, save to GitHub,
drafts with flags. Built per sport from the sport folder's spec.
- **Model:** Opus for the shared design, Sonnet per sport.

## Stage 8: making it a template others can use
- "Use this template" works out of the box: the sample season shows until the
  league adds its own.
- A setup guide for a non-developer; maybe a `/new-league` Claude Code command
  that asks questions and writes `league.yml`, teams and the schedule.
- A live demo for each sport (the sample leagues on GitHub Pages).
- **Model:** Sonnet, Opus for the guide's review.

## Stage 9: desktop layouts
- **Model:** Sonnet.

## Later
- Printable score sheets per sport (a spec drives the sheet, the rules and the
  entry page, as in the Masters site).
- The photo-reading prompt per sport, copied from the entry page.
- Moving the Masters site onto scorers-table, in an off-season, if it's worth
  it.

## Sessions
Stages 0-2 run in the Masters website session. From stage 3, a new session on
the `scorers-table` repo, so its context is the template and not one league.
Start each stage with: "Read BRIEF.md, PLAN.md and CLAUDE.md, then do stage N."
