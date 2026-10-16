# The league's data files

A guide for whoever keeps the league's numbers up to date. You do not need to be a programmer. Everything
here can be done in GitHub's web editor in a browser, and the site checks your work before anything goes
live.

**The short version.** After each game night, each paper score sheet becomes one small text file. You also
keep a list of teams, a list of players and the schedule. The site reads those files, checks them, works out
every number (standings, leaders, records) and publishes the pages. If something does not add up, the check
fails with a plain message and **nothing is published**. A typo cannot put a wrong number on the site.

- [What lives where](#what-lives-where)
- [The files](#the-files): `league.yml`, `seasons.yml`, `teams.yml`, `players.yml`, `schedule.csv`, `games/`, `drafts/`, `sheets/`
- [How to](#how-to): add a game, cancel or move one, record a forfeit, a bye, a playoff game, a new season
- [Checking your work](#checking-your-work) and [reading an error message](#reading-an-error-message)
- [Still to decide](#still-to-decide)
- [Sample data and the preview copies](#sample-data-and-the-preview-copies)

Which boxes a score sheet has, and what is checked in them, depends on the sport. The box-by-box guide for
your sport is `sports/<your sport>/README.md` (basketball's is `sports/basketball/README.md`). The examples on
this page are basketball, the sport the template ships with, and the teams are the ones in its sample season.
The other sports follow in their own pull requests; the stub (`sports/stub/`, two halves and a Final box) stays
as the core's test sport.

## What lives where

```
league.yml                  the league's settings: name, sport, colours, rules (edit rarely)
data/
  seasons.yml               the list of seasons
  2026-27/                  one folder per season
    teams.yml               the teams
    players.yml             the players
    schedule.csv            every game, played or not (a spreadsheet)
    games/                  one file per finished game
    drafts/                 unfinished games (the site never reads these)
    sheets/                 photos of the paper score sheets
  sample-2026-27/           made-up data, for the sample site (do not edit by hand)
```

Everything outside `data/` and `league.yml` is the website itself. You never need to open it.

## The files

A few rules hold for all of them:

* **Ids** (a team, a player, a game, a season) use lower-case letters, digits and single hyphens:
  `rapids`, `dave-m`, `2026-11-05-1`. An id never changes once a game uses it.
* **Players are always "First L."**, like `Dave M.` Never a full name. No contact details, no photos.
* **Dates** are written `2026-11-05`. **Times** are 24 hours, `19:00`.
* In `.yml` files, a `#` starts a comment. The build ignores the rest of that line.
* A mistake in a key name (`naem:` for `name:`) is an error, not something silently ignored.

### `league.yml`

The league's settings. Every setting is explained in the file itself, in plain words. You must set three:
`name`, `sport` and `timezone`. Everything else has a default.

```yaml
name: "Riverside Masters Basketball"
sport: basketball
timezone: America/Toronto
sample_data: false
```

### `data/seasons.yml`

The list of seasons. Exactly one is `current`. It may be empty (a new league's first season starts empty).

```yaml
- id: 2026-27
  label: "2026–27"
  current: true
  venue: "Main Street Gym"
```

`venue` is used for every game whose schedule row has no venue of its own. Each `id` needs a folder of the
same name in `data/`. The made-up sample seasons are explained [below](#sample-data-and-the-preview-copies).

### `teams.yml`

One line per team.

```yaml
- {id: rapids, name: Rapids, code: RAP}
- {id: pines, name: Pines, code: PIN}
```

`code` is two to four capital letters or digits. `id`, `name` and `code` must all be different for each
team. A team may also have `slot: 3` (which of the six team colours it gets, 1 to 6) or `colour: "#7A4A1E"`
(its own colour).

### `players.yml`

One line per player.

```yaml
- {id: dave-m, name: Dave M., team: rapids, number: 23}
- {id: greg-t, name: Greg T., team: rapids}
- {id: jim-k, name: Jim K., team: null, sub: true}
```

* `number` is a jersey number from 0 to 99. For `00`, put it in quotes: `number: "00"`.
* Two players on a team may not share a number. If two players on a team are both "Dave M.", both need a number.
* A spare who belongs to no team has `team: null` and `sub: true`.
* Someone on one team who fills in for another is fine: mark them `sub: true`, or the check warns you.

### `schedule.csv`

A spreadsheet of every game, played or not. Open it in Excel, Numbers or Google Sheets. When you save, choose
**CSV UTF-8**. The first line names the columns, in any order. Only the first five columns are required.

```
game_id,date,time,home,away,venue,surface,type,round,week,status,moved_from
2026-11-05-1,2026-11-05,19:00,rapids,pines,,,regular,,,,
2026-11-05-2,2026-11-05,20:15,herons,foxes,,,regular,,,,
```

| Column | What goes in it |
|---|---|
| `game_id` | A name that is different for every game, such as `2026-11-05-1` (date, then game number). It never changes, even if the game moves. |
| `date`, `time` | `2026-11-05` and `19:00`. |
| `home`, `away` | Team ids from `teams.yml`. "Home" just means the team listed first. A playoff row may hold other text until the teams are known (see [a playoff game](#a-playoff-game-before-the-teams-are-known)). |
| `venue` | Leave empty to use the season's venue. |
| `surface` | The court, sheet, diamond or pad number (`1`, `2`, `A`). Leave empty if the sport has none (basketball has none). |
| `type` | `regular` (or empty) or `playoff`. |
| `round` | The playoff round, shown as written: `Semifinal`, `Final`. |
| `week` | The game night's number. Leave empty and it is counted from the regular-season dates. |
| `status` | Empty, or `cancelled`. |
| `moved_from` | The old date of a game that moved. |

A team can play only one game a day unless the sport allows more. Add every game of the season at the
start, so the site can show what is coming up.

### `games/`

One file per finished game, named after the game id: `games/2026-11-05-1.yml`. It is a copy of the paper
score sheet. The top part is the same for every sport, and the `sheet:` part is the sport's own boxes. This is
a basketball game cut down to two players a side to fit here (`sports/basketball/README.md` explains every box):

```yaml
game_id: 2026-11-05-1
status: final
home: rapids
away: pines
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  players:                     # the roster rows, top to bottom
    home:
      - {player: dave-m, num: 23, here: true, ft: MMXM, fouls: 2}
      - {player: greg-t, num: 11, here: true, ft: X}
    away:
      - {player: mike-r, num: 7, here: true, ft: M, fouls: 3, tech: 1}
      - {player: jim-f, num: 12, here: true, ft: XM}
  running:                     # the running score: the team's new total -> the scorer's jersey number
    home: {2: 23, 4: 11, 5: 23, 7: 23, 10: 11, 12: 23}
    away: {3: 7, 5: 12, 6: 12, 8: 7, 10: 7}
  lines:                       # the running total each end-of-quarter line is drawn under
    home: [5, 7, 10, 12]
    away: [3, 6, 8, 10]
  boxes:                       # the score boxes under each roster, as written
    home: {q1: 5, q2: 7, q3: 10, q4: 12, ot: null, final: 12}
    away: {q1: 3, q2: 6, q3: 8, q4: 10, ot: null, final: 10}
```

| Line | What goes in it |
|---|---|
| `game_id` | The same as the file name and the schedule row. |
| `status` | `final`. (A game that is not finished goes in `drafts/`.) |
| `home`, `away` | The same two teams, in the same order, as the schedule row. |
| `checked_by` | Who checked the file against the paper sheet, as "First L.". |
| `scorekeeper` | Optional. Who kept score. |
| `notes` | Optional. Shown on the game page: `notes: [{text: "Started ten minutes late."}]`. |
| `sheet` | The sport's boxes. Sides are always `home` and `away`, never team ids. |

Only files in `games/` count. If a file in `games/` has an error, the whole build stops, so a half-finished
file does not belong there.

### `drafts/`

A game you have not finished or checked. Same layout as a game file, with `status: draft`. **The build never
opens `drafts/`**, so a draft cannot break the site. A draft may leave boxes empty. It may also carry notes
for the person who finishes it:

```yaml
review:
  - {at: sheet.boxes.home.final, note: Check this score against the photo.}
```

When the draft is done, move the file to `games/`, change `status` to `final` and delete the `review` lines.

### `sheets/`

Photos of the paper score sheets, named after the game: `sheets/2026-11-05-1.jpg` (or `.png`, `.pdf`). They
stay in the repository so you can check a file against its sheet. They are **not** shown on the site, unless
you set `photos: true` in `league.yml`.

## How to

You can do all of this in GitHub's web editor: open the file, click the pencil, change it, and choose
"Create a new branch and start a pull request". The checks run on the pull request (see
[Checking your work](#checking-your-work)).

### Add a game after a game night

1. Make sure the game is a row in `schedule.csv`.
2. Create `data/<season>/games/<game_id>.yml` and copy the paper sheet into it, box for box.
3. Set `checked_by` to the person who compared the file with the paper sheet.
4. Put the photo in `sheets/` under the same name.
5. Open the pull request. If the checks are green, merge it. The site updates in a couple of minutes.

### Fix a wrong number

Edit the game file and merge. Standings and stats are always worked out again from the files, so there is
nothing else to correct. Never edit anything in `_data/computed/`: it is rewritten on every build.

### Cancel a game

In `schedule.csv`, write `cancelled` in the `status` column. The game stays on the schedule, marked as
cancelled, and calendar apps show it as cancelled. A cancelled game **cannot have a game file**, so
delete the file if one exists.

```
2026-10-29-2,2026-10-29,20:15,herons,foxes,,,regular,,,cancelled,
```

### Move a game

Change `date` and `time` in the schedule row and write the old date in `moved_from`. **Keep the `game_id`**
(and the file name, if the game was already played). The id never changes, so calendar apps update the
event in place.

```
2026-12-17-2,2026-12-22,20:15,foxes,pines,,,regular,,,,2026-12-17
```

### Record a forfeit

The game file has no `sheet`. It names the team that forfeited instead:

```yaml
game_id: 2026-10-22-1
status: final
home: foxes
away: pines
checked_by: Lee M.
forfeit: pines
```

No player gets a game played or any stat. How a forfeit counts (the score, and whether it earns period
points) is a league decision, set under `standings: forfeit:` in `league.yml`. Until you set it, the site
shows `[placeholder]` and the build lists it under "Still to decide" (basketball's usual rule is 20 to 0).

### A tie

Whether a regular-season game may end level is the league's to decide (`standings: ties:` in `league.yml`;
basketball starts with no ties, shown as `[placeholder]`). Where ties are allowed, write the game file as it
is and the standings show a tie. Where they are not, the check stops the build at the Final box and says so.
A **playoff game can never end tied**, whatever the setting. If the sport has overtime, the sheet records it
first: basketball's README has the details (a game level after Q4 goes to overtime, and only one still level
after that is a tie).

### A bye

You never write a bye. When a team has no regular-season game on a game night, the site works that out from
the schedule and shows "Bye". A team whose game was cancelled is not shown as having a bye.

### A playoff game before the teams are known

Add the row now so the schedule is complete. Set `type` to `playoff` and put any text in `home` and `away`:

```
2027-01-07-1,2027-01-07,19:00,1st,4th,,1,playoff,Semifinal,,,
2027-01-07-2,2027-01-07,20:15,2nd,3rd,,2,playoff,Semifinal,,,
2027-01-14-1,2027-01-14,19:00,Winner SF1,Winner SF2,,1,playoff,Final,,,
```

Only a playoff row may name a team that does not exist yet. When the teams are known, replace the text with
the team ids. Playoff games never count in the standings. Players' playoff stats are kept apart from their regular-season ones.

### Add a player or a spare

Add a line to `players.yml` (see [above](#playersyml)). Mid-season, a new player does not change anything
that was already played. Players show up on game files by their `id`.

### Start a new season

1. Make a folder `data/2027-28/` with `teams.yml`, `players.yml`, `schedule.csv`, `games/` and `drafts/`.
   Empty files are fine.
2. In `data/seasons.yml`, add the season and move `current: true` to it. Exactly one season is current.
   The old season moves to the archive on its own.
3. Team and player ids may repeat from last year. Game ids must not.

If next year's rules differ (say, a new points rule), put them under `overrides:` for the new season only.
The archive keeps showing last year's standings under last year's rules.

## Checking your work

The check is the same everywhere:

* **On a pull request**, the "Build and deploy" check runs by itself. A red cross means a problem. Click
  "Details" and the log lists every one. GitHub also lists each problem, with its file, in the check's summary.
* **On your own computer**, run `python scripts/build.py --check` (it needs Python 3.12 and
  `pip install -r requirements.txt`). It reads everything, checks it, and writes nothing.

The run lists **all** the problems at once, not just the first. Fix them, push again, and the check re-runs.
A **warning** does not stop the build: it is something worth a look. An **error** stops the build and
nothing is published.

## Reading an error message

Every problem is one line:

```
file: path: message
```

* **file** is the file with the problem.
* **path** says where in the file. The parts are joined with dots. Numbers count from 0, so `0` is the
  first player in a list, `1` the second.
* **message** says what is wrong, and usually what to do.

Real examples:

```
data/sample-2026-27/games/2026-11-05-1.yml: sheet.boxes.away.final: the Final box says 68, but the running score ends at 67
data/sample-2026-27/games/2026-11-05-1.yml: sheet.players.home.0.player: player 'noa-q' is not in players.yml
data/sample-2026-27/games/2026-11-12-2.yml: home: comets/comets doesn't match schedule.csv (pines/comets). Fix the file, or the schedule row.
data/sample-2026-27/players.yml: 1.name: 'Max Turner' should be 'First L.' (a first name and the last initial, never a full name).
data/sample-2026-27/schedule.csv: 1.home: 'fox' is not a team id in teams.yml. Did you mean 'foxes'? Only a playoff game may name a team that is not known yet, like TBD or 1st. (spreadsheet line 3).
```

The first one: in the file for game 2026-11-05-1, the `sheet`'s Final box (`boxes`, `final`) for `away` says
68, but the running score on the sheet ends at 67. Which is wrong, the Final box or the running score? Check
the paper sheet.

The path `sheet.players.home.0.player` reads: in the `sheet`, the `players`, for `home`, the first row (0), the
`player` box. For `schedule.csv`, row 0 is the first line under the header. The message also gives the
spreadsheet line (`spreadsheet line 3`), the number you see in Excel or Google Sheets.

A path of `1.name` in `players.yml` means the second player's `name`. A path that is empty means the whole file.

| If the message says | Usually |
|---|---|
| `... is not a known key here. Did you mean ...?` | A typo in a line's name. |
| `... is not a team id in teams.yml` | A typo in `schedule.csv` or a game file, or the team is not in `teams.yml` yet. |
| `... is not a game in schedule.csv` | The game file's name does not match any `game_id`. Add the schedule row first. |
| `... doesn't match schedule.csv` | The game file's `home` and `away` are not the schedule row's. |
| `... is marked cancelled in schedule.csv, so it cannot have a game file` | Delete the file, or clear the `cancelled`. |
| `... is not valid YAML` | A missing colon or a wrong indent, with a line number. |
| `... should be 'First L.'` | A full name where only a first name and last initial are allowed. |
| `... is 'draft', but the build reads only finished sheets` | Move the file to `drafts/`, or finish it. |

The sport's own boxes (everything under `sheet.`) have their messages explained in
`sports/<your sport>/README.md`.

## Still to decide

Some rules are the league's to decide: how a forfeit counts, how ties in the standings are broken, whether
there is overtime, how many games a player needs before they are ranked on a leaderboard. The template does
not make these up. If you have not set one, the build uses the sport's usual rule so the site still works,
shows **`[placeholder]`** on the site wherever that rule is described, and prints a list after every build:

```
Still to decide (the site shows [placeholder] until you set these in league.yml):
  - Overtime (rules.overtime)
  - Most personal fouls one player can have in a game (rules.foul_limit)
  - Ties (standings.ties)
  - Forfeit (standings.forfeit)
  - Tiebreakers (standings.tiebreakers)
  - Minimum games for the points per game leaders (stats.minimums.ppg_min_games)
  - Minimum free throw attempts for the free throw % leaders (stats.minimums.ft_min_attempts)
```

That is the list for the basketball template as it ships. A sport brings its own list, and a league that has
answered one no longer sees it.

The words in brackets are where to set it in `league.yml`. Setting it, **even to the usual value**, removes
the placeholder:

```yaml
rules:
  overtime: overtime
  foul_limit: 5
standings:
  ties: false
  forfeit: {score: [20, 0]}
  tiebreakers: [head_to_head, diff, points_for]
stats:
  minimums: {ppg_min_games: 0, ft_min_attempts: 10}
```

(Those are the sport's usual values, shown so you can see the shape. Put your own league's answers there.)

`league.yml` lists everything you can set, and `sports/<your sport>/sport.yml` says what each option may be.
You do not have to settle these before the first game: the site works while they are open.
The Rules page has its own `[League rules]` placeholder to fill in.

## Sample data and the preview copies

The template ships with made-up seasons, `sample-2026-27` and `sample-2025-26`, so the site looks lived-in
before there is a real season. Every team, player and score in them is invented. Do not edit them by hand;
`python scripts/make_sample.py` writes them again (and `--check` shows whether they are as the script would
write them).

* `sample_data: true` in `league.yml` makes the whole site show the sample season, with a banner saying so.
  Set it to `false` when your real season is ready to show.
* The sample season's `as_of` date in `seasons.yml` is "today" for made-up data, so the sample always looks
  mid-season, whatever the real date. **The dates themselves do not move.** In a few years the sample's
  dates will look old. That is harmless, but the sample is regenerated for new dates, not edited.
* With `sample_data: false` and `preview: true` (the default), every build also makes a **copy of the site
  from the sample season at `/preview/`**, so you can see how a page looks with games and stats in it. It is
  not linked from anywhere and carries a banner.
* Do you not want the preview? Set `preview: false`. If you delete the sample seasons from `seasons.yml` (and
  their folders in `data/`), the preview is skipped by itself: `scripts/build_preview.sh` prints
  `no sample season in data/seasons.yml: skipping /preview/` and carries on, and the sport previews below still
  build. (A sample season that is listed but broken is still an error.)
* **Sport previews** are a second, separate setting, `sport_previews` (it sits beside `preview` in `league.yml`).
  `/preview/` is *your* league with made-up games; `/basketball/` is the template's own made-up league
  ("Riverside Masters Basketball") for that sport, in the sport's own look, with the sport's usual rules and
  every "league decides" setting showing as `[placeholder]`: what a new league would see. Nothing from your
  `league.yml` reaches it except `timezone` and `time_format`.
  * `sport_previews: true` builds one copy for every sport that has a demo (today only basketball, so
    `/basketball/`; curling, hockey and slo-pitch get theirs when they are added). A list such as
    `[basketball, hockey]` builds just those, in that order, and a name that is not such a sport is an error.
    `false`, or leaving the line out, builds none. The template ships with `true`, so its own site shows
    what each sport looks like.
  * Like `/preview/`, a sport preview is not linked from any of your own pages, so your visitors do not land on
    a made-up league. **Every page of it carries the noindex tag, whatever `search_engines` says**, and it has
    no calendar files. Its banner says it is a sport preview and links to the other sport previews and back to
    the live site; the `/preview/` banner lists the sport previews too, when there are any.
  * They are built on every deploy, so each costs a few seconds of build time and a couple of megabytes of
    site. If you do not want them, set `sport_previews: false`.
  * A sport id may not be one of the site's own top-level paths (`archive`, `assets`, `calendar`, `games`,
    `players`, `preview`, `rules`, `schedule`, `sheets`, `stats`, `teams`).
  * To build them on your own computer, run `bundle exec jekyll build` and then `scripts/build_preview.sh` (it
    builds `_site/preview/` and `_site/<sport>/`, then puts your own data back).

The made-up data and the real data never mix: the real season's files live in `data/<season>/`, the sample
in `data/sample-<season>/`.
