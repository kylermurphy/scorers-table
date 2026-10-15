# scorers-table: brief

A free, public template for a small recreational league's website: standings,
schedule, results, player stats and past seasons, built from the league's own
paper score sheets. Made for volunteer-run leagues of older players (masters,
old-timers, seniors, rec), where one volunteer keeps the numbers and most
visitors look on a phone.

It grows out of the Masters Basketball League site
(`tb-masters-basketball/website`, live at mastersbasketball.ca), which has run a
real league this way since October 2026. That repo stays as it is; scorers-table
takes what worked and makes it work for any sport.

## Who it's for

- **The volunteer who keeps the stats.** No coding. Types a game up on an entry
  page that looks like the paper sheet and checks it as they type, or pastes in
  what an AI chat read from a photo of the sheet. Saves it to GitHub from the
  browser.
- **The person who sets it up.** Comfortable clicking "Use this template" on
  GitHub and filling in a few files (or answering questions in Claude Code).
  Not a developer.
- **Players and families.** Check standings, last week's scores and their own
  numbers on a phone. Many are 50+: big enough type, high contrast, no clutter.

## What every league gets (the core)

Same for every sport:

- **Seasons**, current and archived. Each season: teams, players, schedule,
  game files. Past seasons keep standings, leaders and results.
- **Teams**: name, short code, colour.
- **Players** shown as "First L." with an optional number. Never full names,
  contact details or photos. This is the default and the template says why.
- **Schedule**: game days (or draws), times, venue and surface (court, sheet,
  rink, diamond), byes, cancelled and moved games, playoffs kept apart.
- **Standings**: a points rule and tiebreakers set in one config file per
  league, with the sport's usual rule as the default.
- **Results and game pages**: the line score (by quarter, end, period or
  inning) and the sport's player lines.
- **Player stats**: the sport's stats, leaderboards with minimums.
- **Calendars**: an .ics per team and for the league.
- **Sample-data switch**: a made-up season shown with a banner, so a new league
  can see the whole site before its first game. A hidden `/preview/` copy.
- **Search engines**: a setting. Off (noindex) by default, since many leagues
  don't want their players findable; one line to turn it on.
- **No analytics, ads, trackers or cookie banners.**
- **Light and dark**, following the phone's setting, with a button to switch.
- **Works at 360 px**, WCAG AA contrast, 44 px touch targets, every page usable
  with JavaScript off (the entry page excepted: it's a tool).

## What changes by sport (a sport folder)

Each sport is a folder that says:

- the **game file**: a box-for-box copy of that sport's score sheet;
- the **rules** that check a game file (one place, with a JavaScript copy for
  the entry page, both run against the same test files);
- the **stats** worked out from it, and which get leaderboards;
- the default **standings points and tiebreakers**;
- the **line score** shape and the game page's player tables;
- its **score sheet** (a printable PDF), later;
- its sample season generator.

### Typical club rules (the defaults)

These are the defaults for a new league of that sport. Every one is a setting,
and the template shows a visible `[placeholder]` wherever a league has to
decide.

**Basketball** (from the Masters league, generalised)
- 4 quarters, overtime if tied. Running score sheet: each basket's scorer by
  jersey number, free-throw circles, fouls.
- Stats: GP, points, PPG, FTM, FTA, FT%, fouls, technicals.
- Standings: 2 points a win (option: the Masters rule of 1 per quarter won and
  3 per win). Ties only if the league allows them.

**Curling** (club league)
- Teams ("rinks") of four: lead, second, vice, skip; spares are common.
- 8 ends (6 for many daytime and senior leagues). One team scores per end, or
  the end is blank. Hammer (last rock) goes to the team that didn't score; a
  blank end keeps it. An extra end if tied, where the league plays one;
  otherwise a tie. A team may concede ("shake hands") early: the score stands
  as it is.
- Line score: points by end for each team, hammer marked, blanks shown. Option:
  the club scoreboard style (end numbers hung under the running score).
- Stats are team stats: points for and against, ends won, stolen ends (scored
  without hammer), blank ends, big ends (3+). Players: games played and
  position; spares listed.
- Standings: 2 for a win, 1 for a tie. Tiebreakers: head-to-head, then points
  for and against `[placeholder]`.
- Schedule words: "draw" for a game time, "sheet" (A-D) for the surface.

**Hockey** (old-timers / rec, non-contact)
- Rosters of 12-15 skaters and a goalie; spares, including spare goalies.
- 3 periods. Ties allowed in the regular season (option: overtime or a
  shootout, with an OT loss column).
- Game sheet: roster with numbers; scoring summary (period, time, goal by #,
  up to two assists by #); penalties (period, time, #, infraction, minutes);
  goalie for each team; score by period.
- Stats: GP, G, A, PTS, PIM; goalies: GP, GA, GAA, shutouts, record.
- Optional caps some leagues use (goals a player may score in a game)
  `[placeholder]`.
- Standings: 2 for a win, 1 for a tie (or an OT loss). Tiebreakers: wins, then
  head-to-head, then goal difference `[placeholder]`.

**Slo-pitch** (rec / masters, often co-ed)
- 7 innings, a run limit per inning (often 5, last or "open" inning
  unlimited), a mercy rule and a time limit `[placeholder]`. Home run limits
  `[placeholder]`. Co-ed batting order rules `[placeholder]`.
- Line score: runs by inning for each team (R, plus H and E where kept).
- Stats are optional by league: team results only, or a basic batting line
  (AB, R, H, RBI, HR, BB, AVG).
- Forfeits common (scored as a set result, such as 7-0 `[placeholder]`).
- Standings: 2 for a win, 1 for a tie. Tiebreakers: head-to-head, then run
  difference (often capped) `[placeholder]`.
- Schedule words: "diamond" for the surface.

## Layouts

A league picks one of six layouts and adds its own colours and logo. All six
use the same pages and parts; a layout changes the look and the arrangement,
not the data.

| Layout | Kind | Starting point |
|---|---|---|
| **Basketball** | sport | "6 Recommended" from the Masters design canvas (the live site), with the Thunder Bay badge and Sleeping Giant replaced by the league's logo and a neutral scene |
| **Curling** | sport | new: ice, the house rings, the end-by-end line score as the hero |
| **Hockey** | sport | new: rink boards, scoring summary, goals/assists/points |
| **Slo-pitch** | sport | new: diamond and scorebook feel, inning line score |
| **Classic** | general | "1 Classic Club" from the Masters canvas: white page, one brand-colour bar, the safe choice |
| **Scoreboard** | general | "4 Scoreboard" from the Masters canvas: loud, arena numbers, standings as a race, leaders as a ranked list |

The four sport layouts are the default for their sport; any sport can use any
layout. Phones first; desktop after.

**Light and dark:** every layout has both, following the phone's setting with
a button to switch. Dark is a colour swap, never a different structure; each
layout's dark palette is on the design canvas.

**Desktop:** one shared desktop grid for all six layouts (the Masters site's:
header on one row, a main column of about two thirds for results and
standings, a side column for the next game day and leaders). Layouts only
re-skin it. Game pages use the width for the two teams side by side (and, for
hockey, the scoring summary beside the penalties). So phone components are
built to stretch, and desktop stays a late stage.

Design canvas for scorers-table (phone, light and dark):
https://claude.ai/artifact/WUVtsLg2GDS5fVa8KzqJAN

Masters design canvas ("TB Masters Basketball — Site Directions"):
https://claude.ai/artifact/BaXVw5DEwLEePb3chLk3c5

## What carries over from the Masters site

What worked, and should be kept:

- **Data files are the source of truth** (YAML and CSV in `data/`), edited
  through the entry page or by hand, one file per game.
- **A Python build step** checks every file and works out every number before
  Jekyll builds the pages; it stops with every problem listed, each naming the
  exact box (`running.bb.14`).
- **The rules live in one place** (Python), ported to JavaScript for the entry
  page, with shared test files so the two never drift.
- **Generated stub pages** give one page per game, player, team and season
  without a Ruby plugin, so it builds with GitHub Actions and Pages.
- **The entry page**: the paper sheet as boxes, checks as you type, saves to
  GitHub, drafts with review flags, paste from an AI chat.
- **Reading a photo**: a prompt for ChatGPT or Claude (copied from the entry
  page) that reads the sheet section by section, draws a check picture and
  flags anything unsure; "a wrong number is worse than a flag".
- **Printable score sheets** made from one spec, so the sheet, the rules and
  the entry page agree on every box.
- **Never invent league facts**: a visible `[placeholder]` and a list of open
  questions.

What to leave behind: everything specific to Thunder Bay or to the Masters
league (the badge, the Sleeping Giant, form MBL-SS6's exact layout, the
quarter-points standings rule as a default, the `/record-game` photo-measuring
helper, which is tuned to one sheet).

## Sample leagues

Made-up names only, nothing that looks like a real league or club:
for example "Riverside Masters Basketball", "Pine Lake Curling Club",
"Northside Old-Timers Hockey", "Maple Park Slo-Pitch". Plain placeholder logos.

## Not decided yet

- ~~Licence~~: MIT.
- ~~Search engines default~~: off (noindex), decided October 2026.
- ~~Setup help~~: a written guide only, decided October 2026. No `/new-league`
  command for now; it can come later if leagues ask for it.
- ~~Desktop~~: stays at stage 9; phone first until then (decided October 2026).
