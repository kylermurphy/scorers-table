# Landing page: plan

A plan for the front page of the template's own site (`kylermurphy.github.io/scorers-table/`). Nothing is built
yet. Part A is for the owner (about 3 minutes); part B is the detail the builders and the reviewer work from.

Already decided by the owner, and not reopened here: `/` becomes a landing page that shows and links to the
sports; the basketball demo moves off the root to `/basketball/` (it is already there) and curling stays at
`/curling/`; the page uses the Basketball look; each sport card has a name, a one-line description, a link to
its demo and a live mini-preview built from that sport's sample season; hockey and slo-pitch show as "coming
soon" with no link; the page links to the setup guide and the GitHub repo; a real league turns the landing page
off with one setting and gets its own site at the root, as today.

# Part A: for the owner

## The short version

- **One new setting**, `landing_page` in `league.yml`. `true` puts the landing page at the root; `false`, or
  leaving the line out, gives a league's own site at the root, exactly as today. The template ships `true` (its
  own site is the showcase).
- **With the landing page on, the root has only the landing page** (and the "page not found" page). The
  basketball sample league is at `/basketball/` and nowhere else, so nothing appears twice. `/preview/` is not
  built: there is no league site to preview.
- **The mini-previews are real numbers.** Every build works out each sport's made-up demo league the same way
  the demo itself does, and the card shows the top 3 of its standings and its latest result. Nothing is typed in
  by hand, so the card always agrees with the demo it links to. (The sample seasons are frozen at their own
  "today", 20 November 2026, so the numbers only change when the sample changes.)
- **Each card shows the sport's own look in its preview box** (curling in the Curling colours and fonts), inside
  a page that is otherwise the Basketball look. This is open question 1: it costs a little more work and about
  90 KB more for the page to load; the plain alternative is everything in the Basketball look.
- **The words live in one small file**, `landing.yml`: the title, the intro, the "get started" links and the
  "coming soon" list. A sport's one-line description lives in its own `sport.yml` (a new `blurb` line). When
  hockey is built, its card appears by itself and the build tells you to take it off the "coming soon" list.
- **Same rules as the rest of the site:** works on a 360 px phone, light and dark with the sun/moon button,
  works with JavaScript off, no trackers, hidden from search engines (`noindex`) unless `search_engines: true`.
- **The demos' banners** say "All sports" (back to the landing page) instead of "Go to the live site".
- **Built in four packages** by Sonnet, two at a time, then reviewed by Opus (part B, section 8).

## Open questions for you

Each has a recommendation; say "as recommended" to take them all.

1. **The sport's own look inside each card's preview box?** Recommended: **yes**. The six looks are what the
   template sells, and the preview box is the one place to show them side by side. Cost: the page loads the
   Curling stylesheet (14 KB) and the Curling fonts (about 72 KB), more as hockey and slo-pitch arrive; the
   sun/moon button needs three more lines of JavaScript to switch the boxes too. Alternative: everything in the
   Basketball look (simpler, but every card looks the same).
2. **What a league that copies the template sees on its first deploy.** The template and the showcase are the
   same repository, so a fresh copy also starts with `landing_page: true` and shows the scorers-table landing
   page until the league sets `false`. Recommended: **accept that, and make it loud**: the `landing_page` line
   goes at the top of `league.yml` beside the three settings everyone must set, with a comment; every build
   with it on prints "The front page is the scorers-table landing page. For your league's own site, set
   landing_page: false in league.yml."; the landing page's "Get started" section says the same; the setup guide
   makes it step 1. (Alternative: a GitHub repository variable that only the showcase has, so a copy needs no
   change. Not recommended: it hides the setting outside `league.yml`, against your "one setting" decision.)
3. **The words.** Recommended drafts (all editable later in `landing.yml` and `sport.yml`):
   - header name **scorers-table**, badge **ST**, tagline **League websites from paper score sheets**;
   - page title **A website for your league, from its score sheets**;
   - intro: **"A free template for a small recreational league: standings, schedule, results, player stats and
     past seasons, kept by one volunteer from the paper score sheets. Each sport below is a working demo with a
     made-up league."**;
   - blurbs: Basketball **"Quarters, a running score, free throws and fouls."**; Curling **"Ends and the hammer,
     steals and blanks, rinks of four with spares."**; Hockey **"Periods, goals and assists, penalties and
     goalies."**; Slo-pitch **"Innings, run limits and an optional batting line."**;
   - a short "What every league gets" list under "Get started" (standings, schedule, results and stats; past
     seasons; phones first, light and dark; players shown as "First L." only; no ads or trackers; hidden from
     search engines unless the league says otherwise), taken from `BRIEF.md`;
   - the menu: **Sports** and **Get started** (both jump down the page).
4. **The setup guide link.** The written guide is stage 8 and does not exist yet. Recommended: link to the
   README's "Publish it" section on GitHub for now, with the label "Setup guide (short version)", and swap the
   link when stage 8 lands (one line in `landing.yml`).
5. **Link the design-system page?** It is not published today (`docs/` stays off the site). Recommended: **not
   now**. Publishing it at `/design-system/` is a separate small decision for later.

# Part B: for the builders and the reviewer

## 1. The switch

`league.yml` gets `landing_page: true | false`. **Default when the line is absent: `false`**, so every existing
copy is unaffected. The shipped template says `true`, written near the top with a comment (question 2).

| `landing_page` | `sport_previews` | Result |
|---|---|---|
| absent / `false` | anything | today's site, byte for byte (section 6) |
| `true` | `true` or a list | landing page at `/`, one card per sport `sport_previews` names, in its order (`true` = every demo sport, sorted by id: basketball, curling), then the coming-soon cards |
| `true` | `false` / absent | **error**: there would be no demos to show |

`preview` and `sample_data` keep their meaning but do nothing at the root while the landing page is on: the
league's own pages are not built there, and `scripts/build_preview.sh` skips `/preview/` and says so in one line.
The league's data is still loaded and checked on every build (the template's own `data/` must stay valid).

Checks (in `scripts/core/config.py`, `league.yml` key list; the `landing.yml` checks in `scripts/landing.py`),
each with its path, worded for a volunteer:

```
league.yml: landing_page: must be true or false.
league.yml: landing_page: the landing page shows the sport demos and links to them, but sport_previews is false
  (or left out), so there are none. Set sport_previews: true, or set landing_page: false to put your league's
  own site at the front page.
landing.yml: landing_page: true in league.yml needs this file (the words of the front page). Put it back from
  the template, or set landing_page: false.
landing.yml: links.1.url: 'githb.com/x' must start with https:// or be a path of this site, like /basketball/.
landing.yml: coming_soon.0: 'hockey' has a demo now, so it gets a real card. Take it off coming_soon.   (warning)
sports/hockey/sport.yml: blurb: a sport on the landing page needs a one-line blurb (at most 100 characters).
```

Plus a note in every build report while it is on (question 2). `landing.yml` is read only when the switch is on,
so a league that deletes it is fine.

## 2. What the root builds

**Recommendation: with the switch on, the root is the landing page and `404.html` only; the league's own pages
are left out of that Jekyll build by a generated config overlay.** Checked against how the copies are made
today: `build_preview.sh` writes a small overlay per copy (`$tmp/<folder>-config.yml`), runs `build.py --out .`
(which swaps `_data/computed/` and the stub folders whole), builds Jekyll with `--config _config.yml,<overlay>
--destination _site/<folder>`, and finally reruns the real `build.py` to put the source back.

- **`build.py`** (a plain run, not `--sport-preview`, not `--check`) always writes `_config.landing.yml`
  (git-ignored). Switch off: one line, `landing_page: false`. Switch on: `landing_page: true`; `exclude:` = the
  `exclude` list read from `_config.yml` plus `index.html`, `schedule/`, `stats/`, `teams/`, `archive/`,
  `rules/`, `calendar/`, `sheets/` (the score sheet photos `photos: true` writes; and minus `landing/`); `include: []`; and `output: false` for the four collections.
  Jekyll replaces lists when it merges configs, which is why the list is copied from `_config.yml` at every
  build rather than written by hand (no drift).
- **The page source** is `landing/index.html` with `permalink: /`. `_config.yml` adds `landing/` and
  `landing.yml` to its `exclude`, so the league build and every preview copy never see it.
- **`build.py` stays additive**: with the switch on it still writes the league's own computed files and stubs as
  today (the restore at the end of `build_preview.sh` is therefore unchanged), and adds
  `_data/computed/landing.json`. Jekyll simply does not render the league pages at the root.
- **CI step 6** becomes `bundle exec jekyll build --config _config.yml,_config.landing.yml,_config.ci.yml
  --baseurl "$BASE_PATH"` (`_config.ci.yml` stays last: it only carries `url`).
- **`build_preview.sh`**: skips `/preview/` when the switch is on; its copy overlays get one more line,
  `live_landing: true`, so a demo's banner says "All sports" instead of "Go to the live site" (same link target,
  `<BASE_PATH>/`). The sport copies still use `_config.yml` plus their own overlay, so `landing/` never reaches
  them and `/basketball/` and `/curling/` are unchanged apart from that banner wording.
- **`404.html`** stays at the root and prints the landing page's menu (section 4).
- **`check_links.sh`** is unchanged: it runs after `build_preview.sh`, so the landing page's links into
  `/basketball/...` and `/curling/...` are checked; the GitHub links are external and not checked.
- **Local preview**: `bundle exec jekyll serve` alone shows the league site as before. With the switch on,
  `build.py` prints the command for the landing page: `bundle exec jekyll serve --config
  _config.yml,_config.landing.yml` (and `scripts/build_preview.sh` after a build for the demos it links to).
- `SITE_PATHS` in `scripts/core/sports.py` gains `landing`, so no sport can be called that.

Rejected: a Liquid `if` in `index.html` (the other league pages would still be built, so the sample league would
sit at `/schedule/` and `/basketball/schedule/`); a separate temporary source folder for the root (a second
copy of every include path to keep in step, and the CI command changes shape).

## 3. Where the mini-previews get their numbers

New `scripts/landing.py`, called by `build.py` after the checks pass and before writing. For each id the switch
shows it calls `preview_root.write_root(id, <temp>)`, then `load_league`, `load_data` and `compute(...,
sport_preview=<name>)` on that root, exactly as `/<id>/` is built (same fixed seed, same `as_of`), and keeps a
small extract. Measured here: about 2 s per sport (basketball 1.1 s root + 0.9 s compute; curling 0.7 s + 0.5 s).

`_data/computed/landing.json`:

```
shell:   {name, short_name, code, layout: "basketball", tagline, lang, search_engines, footer_name, footer_line,
          nav: [{label, url, key}], footer_links: [{label, url}], labels, extra_layouts: ["curling"]}
active:  {sample_mode: false, preview: false}
intro:   {eyebrow, title, text}
links:   [{label, url, note}]          features: [text]
sports:  [{id, name, blurb, url: "/basketball/", demo_label: "Open the Basketball demo", league_name,
           layout,                                       # the demo's own look (the sport's default_layout)
           window: {
             league:    {name, layout, labels, words, display, results_legend},   # the demo's league.json fields the parts read
             standings: {columns, rows, note},           # top 3 rows; columns up to and including the key column
             teams:     {id: {name, code, slot, colour, url}},                  # the teams the window prints
             latest:    {label, date_long, game}}}]      # the first game of the latest day, from games.json
coming_soon: [{id, name, blurb}]
```

- Every `url` inside a window is rewritten to the demo (`/games/x/` becomes `/basketball/games/x/`), so the
  result card links into the demo. URLs stay site paths for `relative_url`.
- Columns "up to and including the key column" is the sport-neutral way to fit 360 px: basketball shows
  GP W L PTS, curling GP W L T PTS. The standings note is the build's own line, e.g. "Top 3 of 6 · through Thu
  Nov 19", not the long points sentence with its placeholders.
- **Includes never test the sport.** The new part `_includes/parts/sport-card.html` saves `league` and `stats`,
  assigns the window's `league` and `{teams, standings}` to them, includes the existing
  `parts/standings.html` and `parts/result-card.html` unchanged, and restores both. It reads only
  `landing.json`.

**The sport's look in the window (question 1).** Tokens are scoped to the element that carries `data-layout`
(`tokens.css`, `layouts/*.css`, and the design-system page already sets several side by side), so the window is
`<div class="st-page st-sport-card__window" data-layout="curling">` and the curling roles apply inside it.
Three things make it work:

- `head.html` loads each layout in `shell.extra_layouts` after the page's own layout file (attribute-scoped, so
  their order does not matter). Cost today: `curling.css` 14 KB, plus Alegreya 43 KB and Source Sans 3 29 KB
  when the window uses them.
- Dark mode: the layouts' dark rules match `[data-layout=x][data-theme=dark]` on the same element, so the window
  needs the page's `data-theme` copied onto it. `site.js` copies it on every press; a one-line inline script at
  the end of the sport list applies a saved choice before the first paint. With JavaScript off neither has
  `data-theme` and both follow the phone's setting, so they always agree.
- Leaks: a rule like `[data-layout="basketball"] .st-x` also reaches inside the window. Today none touches the
  standings table, result card, chip or line score (only `.st-final`, the race, the header and footer, and a
  `[data-league-colour]` rule the showcase never uses); a new test fails if one ever does.

Contrast: inside the window every pair is the sport layout's own, already measured; the card around it uses
existing roles (text, muted and button on surface). No opacity for "coming soon" (it would break contrast);
any new text-on-ground combination gets a `PAIRS` entry in `scripts/check_contrast.py`.

## 4. The page (phone first, 390 px)

```
[skip link]  header: ST badge · scorers-table · "League websites from paper score sheets" · sun/moon
             menu: Sports · Get started
intro        eyebrow "Free website template", h1 title, two sentences            (shell/page-title.html)
h2 Sports    one card per demo sport, then the coming-soon cards                 (shell/section-head.html, .st-list)
  ┌ Basketball (h3) ───────────────────────┐
  │ Quarters, a running score, free throws… │
  │ ┌ window, in the sport's look ────────┐ │
  │ │ Riverside Masters Basketball · made-up league │
  │ │ Standings: rank, chip, team, GP W L PTS (3 rows) │
  │ │ Latest result: Week 6 · Thu Nov 19    │ │
  │ │ [result card, links to the demo game] │ │
  │ └───────────────────────────────────────┘ │
  │ [ Open the Basketball demo › ]  (44 px)  │
  └────────────────────────────────────────┘
  ┌ Hockey (h3) · Coming soon ──────────────┐   no link, no window
h2 Get started   Setup guide · The code on GitHub (kylermurphy/scorers-table) · "What every league gets" list ·
                 "Copying this template? Set landing_page: false in league.yml."
footer       ST · scorers-table · Basketball demo · Curling demo · Setup guide · GitHub · credit
```

- Header, footer, skip link, theme button and 404 reuse the shell includes: `core/context.html` assigns
  `league = landing.shell` and `active = landing.active` when `site.landing_page` is true, so the existing
  includes print the landing menu and footer and no sample banner. Each window says "made-up league" instead.
- One `h1`; `h2` per section; `h3` per sport. The demo link text names the sport; the card itself is not one big
  link (the result card inside already is one).
- Every path through `relative_url`; external links only to GitHub. `noindex` follows `search_engines` (default
  off); the demos stay `noindex` always.
- At 1440 px the cards sit in the main column as on every page today (the desktop grid is stage 9).
- **Design system first** (CLAUDE.md): the sport card is a new part, so it gets a specimen on the design-system
  page (a demo card with a Basketball window and one with a Curling window, plus a coming-soon card, in the
  Basketball frame, light and dark), its CSS in `parts-shell.css` (roles only), any contrast pairs, and a parity
  case, before the page uses it.

## 5. Describing a sport

- `sport.yml` gets an optional `blurb:` (text, at most 100 characters): the one-liner. Required for a sport
  with a demo by `tests/test_sport_contract.py`, so a new sport cannot reach the landing page without one. The
  card's name is the existing `name:`; the demo league's name is `sample.py`'s `LEAGUE_NAME`.
- `landing.yml` (repo root, excluded from the site) holds the page's own words and the planned sports:
  `name, code, tagline, eyebrow, title, intro, nav, links, features, coming_soon: [{id, name, blurb}]`. The
  first line says it is used only with `landing_page: true` and that a league may delete it.

## 6. Tests, CI and docs

- **Unit** (`tests/test_config.py`, new `tests/test_landing.py`): the switch's values, default and the
  `sport_previews` error; every `landing.yml` check with its path; `landing.json` rows and latest game equal the
  `/<sport>/` copy's own `standings.json` and `games.json`; window URLs all start with `/<sport>/`; a coming-soon
  id that has a demo is dropped with the warning; the overlay's `exclude` is `_config.yml`'s plus the league
  pages. Golden: `tests/golden/landing/landing.json` (`UPDATE_GOLDEN=1`, read by eye).
- **Jekyll** (`tests/test_jekyll.py`, the CI chain in a temporary copy under a base path): `/` is the landing
  page; its demo links reach `/club/basketball/` and `/club/curling/` and those pages exist; no `/schedule/`,
  `/stats/` ... `/games/` and no `calendar/` at the root; coming-soon cards have no `<a>`; no request to another
  site; `noindex`; one `h1`; the window carries `data-layout` and the extra stylesheet is linked; the demos'
  banners say "All sports"; no `/preview/`; no Jekyll "Conflict" warning.
- **Off means unchanged**: with the line absent, (a) every existing golden file is unchanged, (b) the Jekyll
  output with `_config.landing.yml` (off) is byte for byte the same as without it, for the root and for
  `build_preview.sh`'s copies, and (c) the existing Jekyll tests pass untouched apart from the helper below.
- **Test helpers**: the shipped `league.yml` will say `landing_page: true`, and a key written twice is an error,
  so the helpers that copy it (`test_build.py`, `test_calendars.py`, `test_golden.py`,
  `test_empty_player_group.py`, `tests/stub_root.py`, `test_jekyll.py`) switch it off through one shared
  helper in `tests/conftest.py`, as they already do for `sport_previews`.
- **Parity and contrast**: the sport-card parity case; `check_contrast.py --check`; the CSS leak test.
- **CI** (`.github/workflows/build.yml`): step 5's comment (also writes `landing.json` and
  `_config.landing.yml`), step 6's config list, step 7's comment (no `/preview/` with the landing page on;
  demos' banners say "All sports"), step 8's comment (the landing page's links into the demos are checked here).
- **Docs**: `README.md` (what the front page is, the switch, local preview commands, a row in the Previews
  table), `docs/data.md` (`landing_page` under `league.yml`; the preview section), `docs/sports.md` (`blurb`;
  a new sport appears on the landing page by itself), `docs/design.md` (the sport card and the window rule),
  `CLAUDE.md` (the new files, `_config.landing.yml` is generated), `PLAN.md` (status; stage 8's "live demo per
  sport" exists and the landing page links them; the guide link to swap), `docs/open-questions.md` (a section
  for this plan's questions and answers), `league.yml`'s comment, `.gitignore`.

## 7. Risks

1. **A copied template's first deploy shows the showcase**, not the league (question 2). Mitigated by the
   placement of the line, the build note, the page's own sentence and the guide.
2. **Old root links break on the showcase site**: `/schedule/`, `/stats/` ... at the root become "page not
   found", which lists the sports. Acceptable: the site is new and nothing links there except the demos'
   banners, which point to `/`.
3. **The overlay's exclude list**: a league page added later to the root (say `/enter/` in stage 7) must be
   added to the landing exclusions, or it shows at the root under the showcase. The test lists the root's pages
   and fails on any it does not expect.
4. **The window CSS** (only with question 1 = yes): a later layout rule could leak into windows, or the theme
   copy could miss a window. Covered by the leak test, the Jekyll test and the 390 px screenshots in both themes.
5. **Build time**: about 2 s more per demo sport on every main `build.py` run while the switch is on; nothing
   when it is off (tests switch it off, so the suite does not slow down).
6. **The demos themselves**: unchanged except the banner wording; their tests keep running with the switch off,
   and one landing test checks the banner wording with it on.

## 8. Build breakdown (Sonnet builders, Opus review)

| # | Package | Owns | Done when | Runs |
|---|---|---|---|---|
| 1 | **Switch and data** | `scripts/core/config.py`, `scripts/core/sports.py` (`blurb`, `SITE_PATHS`), `sports/basketball/sport.yml`, `sports/curling/sport.yml`, new `scripts/landing.py`, `scripts/build.py`, `scripts/preview_root.py` (writes `landing_page: false`), new `landing.yml`, `tests/test_config.py`, `tests/test_sports.py`, `tests/test_sport_contract.py`, new `tests/test_landing.py`, new `tests/golden/landing/` | a temp copy with the switch on writes `landing.json` equal to the demos and the on-overlay; the repo as shipped (switch still absent) writes `landing_page: false` only and every golden file is unchanged; `pytest` green | with 2 |
| 2 | **Sport card part** | `scripts/design_system/specimens_shell.py`, `scripts/design_system/contract.py`, `assets/css/parts-shell.css`, `scripts/check_contrast.py` (pairs, if any), regenerated `docs/contrast.md`, `assets/css/fallbacks.css`, `docs/design-system/index.html`, new `_includes/parts/sport-card.html`, `tests/parity/cases.py` + `cases/sport-card.html`, `assets/js/site.js` (theme copy), new `tests/test_nested_layout.py` (leak test) | parity, contrast and fallbacks checks pass; the specimen at 390 px light and dark looks right; JS-off shows windows following the phone | with 1 (the `landing.json` shape is fixed in section 3) |
| 3 | **Front page wiring** | new `landing/index.html`, `_includes/core/context.html`, `_includes/shell/head.html`, `_includes/shell/sample-banner.html`, `_layouts/default.html`, `_config.yml`, `scripts/build_preview.sh`, `.github/workflows/build.yml`, `.gitignore`, `league.yml` (ships `landing_page: true`), `tests/conftest.py` + the helpers in section 6, `tests/test_jekyll.py` | the CI chain in a temp copy under a base path builds `/`, `/basketball/`, `/curling/` and the link check passes; the off case is byte for byte; screenshots at 360 and 390 px (and one at 1440) in both themes | after 1 and 2 |
| 4 | **Docs** | `README.md`, `docs/data.md`, `docs/sports.md`, `docs/design.md`, `CLAUDE.md`, `PLAN.md`, `docs/open-questions.md` | every new key, file and command documented in plain words; the owner's answers recorded | with 3, once 1 and 2 are merged (names fixed) |

Packages 1 and 2 share no file; 3 and 4 share none. `sports.py` and the golden files are package 1 only;
`test_jekyll.py`, `test_golden.py` and the other helpers are package 3 only.

**Opus reviews**: the overlay and the byte-for-byte off case (the riskiest piece); that the windows' numbers
come from the same computation as the demos; the nested window (leaks, theme copy, contrast, JavaScript off);
the volunteer-facing messages and the first-deploy note; the screenshots against this plan.
