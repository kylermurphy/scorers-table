# Stage 4 spec: the core

Status: **draft for the owner's review**; nothing is built yet. Each numbered section is a decision to
approve or redirect; section 10 lists the ones that need your answer. The only sport in stage 4 is
`stub`, a made-up sport small enough to test every path; stage 5 fills in section 3 four times. The
Masters site (`tb-masters-basketball/website`) is followed unless a "Differs from Masters" note says why.

---

## 1. Repository layout after stage 4

```
league.yml                  the league's settings: the one file a setup person edits (section 2.1)
data/                       source of truth, hand-edited or saved from the entry page (stage 7)
  seasons.yml
  2026-27/                  the real season: empty until the league fills it
  sample-2026-27/           made-up, written by scripts/make_sample.py (committed)
  sample-2025-26/           made-up past season, archive in sample mode only
sports/
  stub/                     sport.yml, rules.py, sample.py, README.md (section 3.7)
scripts/
  build.py                  the build: load -> check -> compute -> write (section 4)
  make_sample.py            writes data/sample-*/ for the league's sport
  core/                     python package: types, problems, config, sports, loader, standings,
                            compute, calendars, writer, fmt
  build_preview.sh, check_links.sh     the /preview/ copy and html-proofer (section 6)
  check_contrast.py, build_css_fallbacks.py, build_design_system.py, design_system/   stage 3, kept
  design_system/contract.py NEW: stage 3 sample data -> computed-JSON shapes (parity test, 5.4)
_config.yml                 Jekyll only: url, baseurl, collections, defaults, exclude
_layouts/                   default, page, game, player, team, archive-season
_includes/core/ shell/ parts/        context, page shell, one include per design-system part (5.2)
index.html  schedule/  stats/  teams/  archive/  rules/index.md  404.html
assets/css/ assets/fonts/   stage 3, kept; two small new parts (5.6)
assets/js/site.js           theme toggle only
assets/league/              the league's logo, if it has one
tests/                      pytest (section 7), with golden/, parity/, fixtures/
.github/workflows/build.yml, Gemfile(.lock), requirements.txt (PyYAML, pytest)
```

Generated and git-ignored: `_data/computed/`, `_games/`, `_players/`, `_teams/`, `_archive/`,
`calendar/`, `sheets/` (only when photos are published), `_site/`.

**Why.** The Masters layout with three moves: league facts leave `_config.yml` for `league.yml`, one file
the build validates (Jekyll would accept a typo silently); each sport is a self-contained folder outside
the Jekyll source; the Python is a `scripts/core/` package instead of one 1,285-line script.

## 2. The data model

Rules for every file: unknown keys are errors (they are usually typos); ids match `^[a-z0-9]+(-[a-z0-9]+)*$`
and never change once a game uses them; every problem names the file and a path inside it (section 4.4).

### 2.1 `league.yml`

| Key | Type | Default | Notes |
|---|---|---|---|
| `name` | text | **required** | "Example Valley Stub League" |
| `short_name` | text | `name` | header name; its last word gets `.st-brand__tint` |
| `code` | 1-4 letters | initials of `name` | the monogram badge when there is no logo |
| `sport` | id | **required** | a folder in `sports/` that has a `sport.yml` |
| `layout` | `basketball curling hockey slopitch classic scoreboard` | the sport's `default_layout` | picks `assets/css/layouts/<id>.css` |
| `colour` | `#RRGGBB` | none | the league colour; runs the contrast gate (4.6) |
| `colour_dark` | `#RRGGBB` | none | only with `colour` |
| `logo` | repo path | none | e.g. `assets/league/logo.svg`; square SVG or PNG of at least 96 px; must exist |
| `tagline` | text | the sport's name | header meta line: `<tagline> · <season label>` |
| `footer_line` | text | the active season's venue | "Thursday evenings · [Gym name]" |
| `contact` | email or URL | none | footer "Contact" link (`mailto:` added to an email); none: no link |
| `timezone` | IANA name | **required** | calendars and "today" |
| `time_format` | `12h` or `24h` | `12h` | |
| `lang` | BCP 47 | `en` | the `<html lang>` (text is English only for now) |
| `search_engines` | bool | `false` | false: `noindex, nofollow` on every page |
| `sample_data` | bool | `false` (the template ships `true`) | the site shows the sample season, with a banner |
| `preview` | bool | `true` | also build the sample copy at `/preview/` |
| `photos` | bool | `false` | publish score sheet photos and link them from game pages |
| `rules` | map | the sport's `options` defaults | sport settings, checked against `sport.yml` (3.2) |
| `standings` | map | the sport's `standings` | see below |
| `stats.minimums` | map | the sport's `minimums` | leaderboard minimums by name |
| `labels` | map | sport and layout labels | override any section label ("Next draw") |
| `calendar.game_minutes` | int | the sport's `game_minutes` | event length in the .ics files |
| `github` | `{repo, branch}` | none | accepted and passed through; used by the entry page in stage 7 |

```yaml
standings:
  rank_by: points            # points | win_pct
  points: {win: 2, tie: 1, loss: 0, ot_win: 2, ot_loss: 1}   # ot_* default to win / loss
  period_points: 0           # points per period won (Masters: 1); a tied period gives none
  ties: true                 # may a regular-season game end tied? (playoff games never may)
  forfeit: {score: [7, 0]}   # or {score: per_period}: 1-0 in every regulation period (Masters)
  tiebreakers: [head_to_head, {diff: {cap: 7}}, points_for]
  columns: [gp, w, l, t, pts, pf, pa, diff]
  playoffs: "[playoff format]"   # the note under the standings
```

**Unset means placeholder.** A setting the sport marks `decide: true` (tiebreakers, overtime, run limit,
minimums...) may be left out. The build then uses the sport's typical-club default, shows `[placeholder]`
wherever the setting is described on the site ("Tiebreakers: [placeholder]."), lists it in
`league.json.placeholders`, and prints "Still to decide" after every build. Setting it, even to the same
value as the default, removes the placeholder. This is how the template honours "never invent league
facts" without refusing to build.

### 2.2 `data/seasons.yml`

```yaml
- id: 2026-27
  label: "2026–27"
  current: true              # exactly one season is current; it may be empty
  venue: "[Gym name]"        # the default venue for schedule rows with a blank venue
  venue_address: ""          # optional, calendar LOCATION
- id: sample-2026-27
  label: "2026–27"
  sample: true               # never current
  stands_in_for: 2026-27     # shown instead of 2026-27 while sample_data is on
  as_of: 2026-11-20          # "today" for a sample season, so it always looks mid-season
  venue: "[Venue]"
- id: sample-2025-26
  label: "2025–26"
  sample: true               # no stands_in_for: a past season, archived in sample mode only
  overrides:                 # optional: this season's own standings / rules / stats.minimums
    standings: {points: {win: 3, tie: 1, loss: 0}}
```
`overrides` deep-merges over `league.yml` for that season only, so changing next year's points rule does
not rewrite last year's archived standings (the Masters site had per-season minimums for the same reason).

### 2.3 Per season

`teams.yml`
```yaml
- {id: otters, name: Otters, code: OTT}               # slot defaults to the row's position (1-6, wraps)
- {id: ravens, name: Ravens, code: RAV, slot: 4}      # slot: the layout's team-colour palette, 1-6
- {id: moose,  name: Moose,  code: MOO, colour: "#7A4A1E"}   # own colour: st-team--custom
```
`code` is 2-4 capitals or digits; `id`, `name` and `code` are unique in the season.

`players.yml`
```yaml
- {id: ann-b, name: Ann B., team: otters, number: 7}
- {id: joe-k, name: Joe K., team: otters}
- {id: sam-p, name: Sam P., team: null, sub: true}    # a spare with no team: sub must be true
- {id: gail-r, name: Gail R., team: ravens, position: skip}   # position: only if sport.yml lists positions
```
`name` is always "First L." (the Masters check, `[placeholder]` allowed); `number` is 0-99 or `"00"`; two
players with one "First L." on a team both need numbers; two regulars on a team cannot share a number.

`schedule.csv`: a header row names the columns, in any order; only the first five are required.

| Column | Meaning |
|---|---|
| `game_id` | unique among the seasons shown; convention `YYYY-MM-DD-N`; never changes, even when the game moves |
| `date`, `time` | `2026-11-05`, `19:00` (24 h in the file; shown per `time_format`) |
| `home`, `away` | team ids; a playoff row may hold any other text (`TBD`, `1st`, `Winner SF1`) until the teams are known |
| `venue` | blank = the season's venue |
| `surface` | `A`, `1`, `2`: the sport's word goes in front ("Sheet A", "Diamond 1"); blank if none |
| `type` | `regular` (default) or `playoff` |
| `round` | playoff round name, shown as written |
| `week` | the game-day number; blank = counted from the regular-season dates |
| `status` | blank or `cancelled` |
| `moved_from` | the old date of a moved game (the row keeps its `game_id`, so calendar events update in place) |

Checks: dates and times parse; teams exist (or are placeholders on playoff rows); a team plays at most
once a day unless the sport allows it (`games_per_day`); a cancelled game has no game file. Byes are
worked out (regular-season teams with no game that day), never written.

### 2.4 Game files

`games/<game_id>.yml` holds finished sheets (`status: final`); `drafts/<game_id>.yml` holds drafts
(`status: draft`) and is **never read by the build** (the entry page checks drafts). Photos stay in
`sheets/<game_id>.jpg|png|pdf` and reach the site only with `photos: true`.

```yaml
game_id: 2026-11-05-1      # core envelope: the core checks every key down to `sheet`
status: final
home: otters               # must match the schedule row
away: ravens
checked_by: Lee M.         # required when final ("First L.")
scorekeeper: Pat S.        # optional
notes:                     # optional, shown on the game page
  - {text: "Played with running time in the second half."}
review: []                 # drafts only: [{at: <path>, note: <text>}]
photo: sheets/2026-11-05-1.jpg   # optional; this is the default
sheet:                     # the sport's payload: owned and checked by sports/<sport>/
  periods: {home: [12, 9], away: [10, 10]}
  final: {home: 21, away: 20}
```

A forfeit replaces `sheet` with `forfeit: <team id that forfeited>` (a `sheet` key is then an error).
Inside `sheet`, sides are keyed `home` and `away`, never team ids, so the same payload checks whichever
two teams play and a sport never needs the team list to read a sheet. ("Home" is only the first-listed
team: pages say "vs", as on the Masters site.)

**Differs from Masters:** the Masters game file mixes the envelope and the sheet at the top level and
keys sides by team id. The `sheet:` block gives the sport a namespace the core never touches, and makes
"which keys does the core own" checkable. The cost is one more path segment (`sheet.home.running.14`).

## 3. The sport-folder interface

A sport is a folder `sports/<id>/` with four required files. No plugin framework: the core finds sports
by listing `sports/*/sport.yml`, and loads `rules.py` and `sample.py` from that folder with
`importlib.util.spec_from_file_location`. Only the league's sport is loaded for a build; the contract test
(section 7) loads every folder.

| File | Required | What it is |
|---|---|---|
| `sport.yml` | yes | everything declarative: words, periods, options, stats, leaderboards, standings defaults, display hints |
| `rules.py` | yes | four pure functions: `check`, `read`, `present`, `derive` |
| `sample.py` | yes | team names and one function that writes a believable sheet |
| `README.md` | yes | the game file format, box by box, with the problem paths (the volunteer's reference) |
| `fixtures/` | stage 5 | shared test files: `<name>.yml` + `<name>.expected.json`, run by the Python and the JS rules |
| `rules.js` | stage 7 | the JavaScript port for the entry page |
| `sheet.py`, spec | later | the printable sheet and its spec |

### 3.1 Types (in `scripts/core/types.py`, imported by sports)

```python
@dataclass(frozen=True)
class Problem:
    level: Literal["error", "warning"]
    at: str            # dotted path into the file: "sheet.final.home", "3.name", "" = the whole file
    message: str       # one sentence, plain words, says what to do
    file: str = ""     # set by the core ("data/2026-27/games/2026-11-05-1.yml")

# Team and Player mirror teams.yml and players.yml (Player.label is "#7 Ann B.").

@dataclass(frozen=True)
class SportContext:          # everything a sport may know, read-only
    sport: dict              # its own sport.yml, parsed
    options: dict            # league rules after defaults and season overrides
    teams: dict[str, Team]   # this season's teams
    players: dict[str, Player]
    sides: dict[str, str]    # {"home": "otters", "away": "ravens"}
    game_type: str           # "regular" | "playoff"
    folder: str              # "games" | "drafts" (a draft may leave boxes empty)

@dataclass
class Score:
    final: dict[str, int]                 # {"home": 21, "away": 20}
    periods: dict[str, list[int | None]]  # regulation periods; None = not played (X)
    extra: dict[str, list[int]]           # overtime / extra ends / extra innings, after the periods
    decided_in: str                       # "regulation" | "overtime" | "shootout"
    final_at: dict[str, str]              # the box holding each final score, for core problems

@dataclass
class Line:                               # one player's counting stats in one game
    side: str                             # "home" | "away"
    player: str                           # a players.yml id
    group: str                            # "player" by default; hockey: "skater" | "goalie"
    counts: dict[str, int]                # keys from sport.yml stats.<group>; gp is the core's

@dataclass
class Reading:
    score: Score
    lines: list[Line]                     # player lines; a player with no line did not play
    team_lines: dict[str, dict[str, int]] # per side: team counting stats (curling ends won...)
    facts: dict                           # anything present() needs later (hammer by end...)
```

### 3.2 `sport.yml`

```yaml
name: Stub                       # shown as the default tagline
default_layout: classic
games_per_day: 1                 # games a team may play on one date
game_minutes: 60                 # default calendar event length
words:
  period: {one: Half, many: Halves, short: H}   # column labels H1, H2
  surface: Court                 # "Sheet", "Diamond", "Pad"; "" when the sport has none
  day: Week                      # "Week 3", or "Draw 3"
  points_for: {label: PF, title: Points for}
  points_against: {label: PA, title: Points against}
line_score: {shape: periods, total_label: Final, corner: Team}   # quarters | ends | periods | innings
options:                         # what league.yml `rules:` may set; validated by type
  periods:  {type: int, default: 2, min: 1, max: 9}
  overtime: {type: choice, values: [none, overtime], default: none, decide: true}
standings:                       # the typical club rule (BRIEF.md); same keys as league.yml standings
  points: {win: 2, tie: 1, loss: 0}
  ties: true
  forfeit: {value: {score: [1, 0]}, decide: true}      # any standings key may be wrapped like this
  tiebreakers: {value: [head_to_head, diff, points_for], decide: true}
  columns: [gp, w, l, t, pts, pf, pa, diff]
stats:
  player:                        # counting stats in Line.counts, summed by the core
    - {key: pts, label: PTS, title: Points}
  derived:                       # rates, worked out by rules.derive()
    - {key: ppg, label: PPG, title: Points per game, places: 1}
  team: []                       # team counting stats in Reading.team_lines
minimums:
  ppg_min_games: {default: 0, decide: true, note: "Minimum {value} games played."}
leaderboards:                    # in page order; tile: true also makes a leader tile
  - {id: pts, of: player, group: player, stat: pts, label: Points, tile: true, edge: hot,
     detail: "{gp} GP"}
  - {id: ppg, of: player, group: player, stat: ppg, label: Points / game, tile: true, edge: accent,
     min: {stat: gp, setting: ppg_min_games, cap_at_team_games: true}, detail: "{pts} pts in {gp} GP"}
labels: {results: Latest results, next: Next game day, leaders: Leaders}
labels_by_layout: {}             # e.g. {scoreboard: {leaders: Buckets}}
display:                         # hints for core parts where a specimen branched on the sport
  card: rows                     # rows | lines (curling and slo-pitch cards hold a line score)
  card_foot: note                # note | meta (curling: "Sheet A · 6:30 PM") | status_note (hockey)
  surface: label                 # label | sub (hockey: "Pad 1" under the time in Classic)
positions: []                    # allowed players.yml positions (curling: lead, second, vice, skip)
```

The core validates `sport.yml` against a fixed schema (`scripts/core/sports.py`), so a stage 5 typo fails
the contract test, not a page. `detail` and `note` strings are Python `str.format` templates over the
row's display values; that is the only templating a sport writes.

### 3.3 `rules.py`

```python
def check(sheet: dict, ctx: SportContext) -> list[Problem]
def read(sheet: dict, ctx: SportContext) -> Reading          # only called when check() found no errors
def present(reading: Reading, ctx: SportContext) -> dict     # display blocks (3.4)
def derive(counts: dict[str, int], group: str) -> dict[str, float | None]   # rates from summed counts
```

* `check` returns **every** problem, paths relative to `sheet` (the core adds `sheet.`), including unknown
  keys, so there is no separate payload schema: the rules stay in one place. For a draft it may downgrade
  "missing" errors to warnings (the entry page will send drafts; the build never does).
* `read` is arithmetic over a valid sheet. The core, not the sport, turns `Score` into wins, ties and
  standings points, so no sport can get the standings rule wrong.
* `present` returns a **closed vocabulary of blocks** that core includes render (3.4); a sport writes no
  Liquid. A new kind of display becomes a reusable core part, with CSS, a specimen and a parity case.
* `derive` serves one game and season totals alike, so the game and stats pages agree (`None` = "—").

All four are pure: no I/O, randomness or clock, only the standard library and `scripts.core.types`, so
the stage 7 JS port can match them line for line.

### 3.4 What `present` returns

```python
{
  "line_score": {                     # the generic line score (renders every stage 3 shape)
    "shape": "periods", "corner": "Team", "total_label": "Final", "extra_label": None,
    "columns": [{"label": "H1"}, {"label": "H2"}],          # + blank, open (flags only when true)
    "rows": {"home": {"cells": [{"v": 12, "won": True}, {"v": 9}], "total": 21, "extra": None,
                      "hammer_first": False},
             "away": {...}},
    "mark_word": None, "won_word": "won the half",            # the hidden words for marked cells
    "legend": [], "note": None},
  "card":   {"note": "Top: #7 Ann B. 9 pts", "strong": "#7 Ann B.", "link_label": "Box score"},
  "tiles":  [],                                               # hero period tiles; None = from line_score
  "blocks": [                                                 # the game page, below the final panel
    {"type": "stat_table", "title": None, "side": "home", "caption": "Otters box score",
     "number_col": True, "columns": [{"key": "pts", "label": "PTS", "title": "Points", "key_col": True}],
     "rows": [{"player": "ann-b", "cells": {"pts": "9"}}], "totals": {"label": "Team · 5 played",
     "cells": {"pts": "21"}}, "note": None},
    {"type": "note", "text": "Points come from the Final box and each player's row."}]
}
```
Cell flags (`won`, `mark`, `blank`, `void`, `open`, `hammer`) map one-to-one onto the stage 3 classes
(`is-won`, `is-mark`, `is-blank`, `is-void`, `is-open`, `svg.st-hammer`). Block types in stage 4:
`stat_table`, `note`. Stage 5 adds `numbers` (curling), `facts` (slo-pitch), `events` and the penalties
table (hockey), `roster` (curling) and `top_performer` (basketball), each as a core part.

### 3.5 The standings engine (core, `scripts/core/standings.py`)

Per regular-season game the core gives each team a **result**: `win`, `loss`, `tie`, `ot_win`, `ot_loss`
(`decided_in` not `regulation`), and **points** = `points[result] + period_points × periods won`
(regulation periods only; a tied period gives nobody a point; the Masters rule is `period_points: 1,
points: {win: 3, tie: 0, loss: 0}`). A forfeit is a `win`/`loss`; its score is `forfeit.score`
(`[7, 0]`), or with `per_period` 1-0 in every regulation period, which also earns period points. Ties:
a tied playoff game is always an error, a tied regular-season game is an error when `ties: false`, both
reported at `Score.final_at`. Playoff games never count in the standings or in season stats.

Columns the engine knows: `gp w l t otw otl pts pct pf pa diff gb pw` (pw = periods won), plus any sport
team stat. `pct` counts a tie as half a win (`.833`); `diff` uses a real minus sign; `gb` shows "—" for
the leader.

**Tiebreakers** are small named functions; each maps every tied team to a sort key (higher is better):

| Name | Key | Notes |
|---|---|---|
| `head_to_head` | win % in games among the tied teams (ties count half) | skipped unless every pair of tied teams has met |
| `head_to_head_points` | standings points per game among the tied teams | same skip rule |
| `wins` | wins | |
| `win_pct` | `pct` | |
| `diff` | points for minus against; `{diff: {cap: N}}` caps each game's margin at N | |
| `points_for` | points for | |
| `points_against` | minus points against | fewer is better |
| `periods_won` | `pw` | the Masters QW column |

Teams are grouped by `rank_by` (points, or win % when teams play unequal schedules). Inside a group the
breakers run **in order, without restarting**: each splits the group by its key and only sub-groups still
tied go on to the next. Teams still level after the last breaker **share a rank** and are listed by name
(the Masters site ranked them by name; a shared rank does not invent a result). Each row records the
breaker that separated it, and `standings.tiebreak_note` says so in a sentence, as on the Masters Home.

### 3.6 `sample.py`

```python
LEAGUE_NAME = "Example Valley Stub League"
TEAMS = [("otters", "Otters", "OTT"), ("ravens", "Ravens", "RAV"), ...]   # made-up names only
def sheet(rng: random.Random, game: SampleGame, ctx: SportContext) -> dict
```
`SampleGame` gives each side's player ids and the outcome wanted (`win_home`, `win_away`, `tie`, `ot`).
The core's `scripts/make_sample.py` does the rest with a fixed seed: teams, made-up "First L." players,
a round robin with a cancelled game, a moved game, a forfeit, upcoming days, playoff rows with
placeholder teams and one draft. It then runs the loader on what it wrote and fails on any problem.

### 3.7 The `stub` sport (built in stage 4)

A made-up sport: two teams, `periods` halves (default 2), a Final box, optional overtime, and who played
with their points. Its whole format:

```yaml
sheet:
  periods: {home: [12, 9], away: [11, 10]}   # one whole number per period, per side
  overtime: {home: 3, away: 1}               # only when rules.overtime is overtime and regulation was tied
  final: {home: 24, away: 22}                # the Final box as written
  players:                                   # optional: who played; pts optional per row
    home: [{player: ann-b, pts: 9}, {player: joe-k}]
    away: [{player: tom-w, pts: 4}]
```

| Check (path relative to `sheet`) | Level |
|---|---|
| a key other than `periods overtime final players` (`<key>`) | error |
| `periods.<side>` missing, not a list, or not exactly `periods` long | error |
| `periods.<side>.<i>` not a whole number 0-99 | error |
| `overtime` present while `rules.overtime` is `none`, or regulation was not tied (`overtime`) | error |
| `overtime.<side>` not a whole number; overtime still tied (`overtime.home`) | error |
| `final.<side>` missing, or not the sum of the periods plus overtime ("the Final box says 24, but the halves and overtime add up to 23") | error |
| `players.<side>.<i>.player` not in `players.yml`; listed twice in the game | error |
| `players.<side>.<i>.player` on another team and not a sub | warning |
| `players.<side>.<i>.pts` not a whole number | error |
| every row has `pts` and they do not add up to `final.<side>` (`players.<side>`) | warning |

`read`: `Score(final, periods, extra = overtime as one-item lists, decided_in = "overtime" if overtime,
final_at = {side: "sheet.final.<side>"})`; one `Line` per player row with `counts {pts}` (0 if absent);
no team lines. `present`: line score shape `periods` with labels `H1 H2 (OT)` and `won` on the higher
cell of each period, a card note naming the top scorer when any `pts` exist, one `stat_table` per side
with players listed, and a `note` block. `derive`: `ppg = pts / gp`, one decimal, half up. Sample:
`LEAGUE_NAME` above, five teams (Otters, Ravens, Badgers, Moose, Lynx), seven players each.

## 4. The build script

`python scripts/build.py` (standard library + PyYAML, Python 3.12). Stages, in order; nothing is written
unless every stage before "write" passes:

1. **Load the league:** `league.yml` -> defaults -> discover and load the sport -> validate `rules`,
   `standings`, `stats` against `sport.yml` -> the colour gate (4.6) -> the logo exists.
2. **Load each season** in `seasons.yml`: seasons rules (one current; samples never current;
   `stands_in_for` names a season; at most one stand-in per season), `teams.yml`, `players.yml`,
   `schedule.csv`, then each `games/*.yml`: the envelope (2.4) -> `sport.check` -> `sport.read`, then the
   core's result checks (ties, playoff ties). Drafts are never opened.
3. **Cross-season:** choose the active season and the archive list (4.3); game ids unique among them.
4. **Compute** per season: schedule days, byes and the next/latest day; results; standings; player and
   team totals (`derive`); leaderboards with minimums; `present` for every game; records; archive rows.
5. **Write** into a temp folder, then swap: `_data/computed/`; the stub pages; `calendar/`; `sheets/` when
   `photos: true`.

Flags: `--check` (stages 1-4, write nothing), `--sample` (force sample mode: the preview copy),
`--today YYYY-MM-DD` (tests), `--site-url URL` (calendar links), `--json` (problems as JSON lines),
`--data DIR --out DIR` (tests). Under GitHub Actions problems are also printed as `::error file=…::`
annotations, so a volunteer sees them on the pull request's changed file.

### 4.1 `_data/computed/` (the contract between Python and Liquid)

Liquid only prints: every number arrives already formatted (`display` strings), every list already
sorted, every URL as a site path for `relative_url`. Raw values sit beside the strings for tests.

| File | Shape (abridged) |
|---|---|
| `league.json` | `{name, short_name, code, sport, sport_name, layout, colour, colour_dark, logo, tagline, footer_line, contact_href, search_engines, lang, nav: [{label, url, key}], labels{}, words{}, display{}, placeholders: [{setting, text}]}` |
| `active.json` | `{season, sample_mode, archive: [ids], today, preview}` |
| `seasons.json` | `[{id, label, sample, current, venue}]` |
| `archive.json` | `[{season, label, sample, url, teams, games, standings_top: [team names], playoff_games: [ids]}]` |
| `calendars.json` | `{season, files: [{team, name, path, webcal, google, download}]}` |
| `<season>/teams.json` | `{id: {id, name, code, slot, colour, url, rank, record, points, sub, players: [ids], results: [game ids], upcoming: [game ids], calendar}}` |
| `<season>/standings.json` | `{columns: [{key, label, title, key_col}], rows: [{rank, team, values{}, display{}, record, tiebreak}], note, tiebreak_note, through, race: {basis, max}}` |
| `<season>/schedule.json` | `{days: [{n, label, date, date_short, date_long, type, venues, state, games: [game row], byes: [team ids]}], latest, next, all_times_pm}`; `state`: played, upcoming, cancelled, partial; game row: `{id, url, time_display, surface, surface_label, home, away, home_name, away_name, status, moved_from_display, round, played, score{home, away}, winner}` |
| `<season>/results.json` | `[{day, games: [ids]}]`, newest day first (Home, the ticker and the hero read this) |
| `<season>/games.json` | `{id: {id, url, type, round, day_label, date_short, date_long, time_display, venue, surface_label, home: side, away: side, tie, forfeit, decided_in, summary, notes, photo_url, standings_points{home, away}, line_score, card, tiles, blocks}}`; side: `{team, name, code, slot, colour, score, result}` |
| `<season>/players.json` | `{id: {id, name, label, number, team, team_name, sub, position, url, groups: {<group>: {totals{}, display{}, ranks{}}}, log: [{game, date_short, opponent, result, score, display{}}], playoffs: {<group>: {...}}}}` |
| `<season>/leaders.json` | `{boards: [{id, label, of, group, stat, tile, edge, min: {value, placeholder, note}, rows: [{rank, player or team, label, team, value, display, detail}], unranked}], table: {group, columns, rows: [ids]}}` |

`results.json` is a separate small file because three parts read it and Liquid sorts poorly. There is
no `playoffs.json`: playoff games are in `games.json` (`type: playoff`) and playoff totals sit under each
player's `playoffs`, kept apart as the Masters site does.

### 4.2 Stub pages

`_games/<game_id>.md`, `_players/<id>.md`, `_teams/<id>.md`, `_archive/<season>.md`: front matter only
(`season`, the id, `title`, `description`), wiped and rewritten every run. Games and archive pages for
every season the archive lists; player and team pages for the active season only, because ids repeat
across seasons (the Masters rule: past seasons show names without links).

### 4.3 Sample switch, active season, preview

* `sample_data: false`: the site shows the `current` season. `true`: the sample season that
  `stands_in_for` it; every page shows the sample banner; other sample seasons join the archive.
* "Today" is the date in `timezone` (or `--today`); for a sample season it is the season's `as_of`. The
  next game day is the first day on or after today with a game not cancelled; the latest is the last
  day with a result. **Differs from Masters** (first unplayed week): visitors see the real next date even
  when a sheet is late. A nightly CI run keeps it current.
* Calendars always come from the `current` season, even in sample mode (nobody subscribes to made-up
  games): one `.ics` per team and `league.ics`, UID from the `game_id`, times written in UTC from
  `timezone` with `zoneinfo` (no hand-written VTIMEZONE), cancelled games kept as `STATUS:CANCELLED`,
  scores in the description, placeholder playoff rows in the league file only.
* `preview: true` and `sample_data: false`: `scripts/build_preview.sh` runs `build.py --sample`, builds
  Jekyll into `_site/preview/` with `baseurl` + `/preview`, then rebuilds the main data. The preview's
  banner links back to the live site.

### 4.4 Problems and exit codes

Every problem prints as `<file>: <at>: <message>`, errors first, grouped by file, then the warnings and
"Still to decide". Paths are dotted into the file and list rows count from 0 (the Masters convention, kept for
the entry page); for `schedule.csv` row 0 is the first line under the header, and the message adds the
spreadsheet line number:

```
league.yml: standings.tiebreakers.1: 'head2head' is not a tiebreaker. Use one of: head_to_head, ...
data/2026-27/players.yml: 3.name: 'Ann Bell' should be 'First L.' (never a full name)
data/2026-27/schedule.csv: 14.home: 'otter' is not a team id in teams.yml
data/sample-2026-27/games/2026-11-12-2.yml: sheet.final.home: the Final box says 24, but the halves add up to 21
data/sample-2026-27/games/2026-11-12-2.yml: home: otters/ravens doesn't match schedule.csv (ravens/otters)
```

| Exit | Meaning |
|---|---|
| 0 | built (warnings and placeholders listed) |
| 1 | data problems: all listed, nothing written |
| 2 | usage or internal error, including a sport function that raised (named with its file and traceback) |

### 4.5 Reused versus new

Reused from stage 3: `check_league_colour` (imported, unchanged), all CSS, the specimens as reference.
Ported from Masters, rewritten sport-neutral: problem paths, loader checks, standings, active/archive
choice, stub pages, atomic write, calendars, preview and link scripts. New: `league.yml`, the sport
interface, placeholders, per-season overrides, block-based game views.

### 4.6 The league-colour gate

When `colour` is set, stage 1 calls `check_league_colour(layout, colour, colour_dark)`. A non-empty list
stops the build (exit 1) and each `problem.message` is printed verbatim (it already names `league.yml`
and the setting); in `--json` it carries `at: colour` or `colour_dark`. A badly formed hex is reported
at the same path. No `colour`: no gate, no attribute, no inline style.

## 5. The Jekyll layer

### 5.1 `_config.yml`, pages, context

```yaml
url: ""                      # CI supplies url and baseurl (section 6); local builds use ""
baseurl: ""
permalink: pretty
future: true                 # stubs are named by date
exclude: [league.yml, data/, sports/, scripts/, tests/, docs/, Gemfile, Gemfile.lock,
          requirements.txt, README.md, BRIEF.md, PLAN.md, CLAUDE.md, LICENSE]
collections:                 # the same for players, teams (/teams/:name/) and archive (/archive/:name/)
  games: {output: true, permalink: /games/:name/}
defaults:                    # layout and nav tab per collection: game/schedule, player/stats,
  - {scope: {type: games}, values: {layout: game, nav: schedule}}   # team/teams, archive-season/archive
```
`search_engines` lives in `league.yml` and reaches the head through `league.json`. No plugins, no
sitemap, no feed. Pages: Home, Schedule, Stats, Teams (index of team cards), Team, Player, Game, Archive,
Archive season, Rules (`rules/index.md`, a Markdown page with a visible `[League rules]` placeholder),
404. Home in stage 4 has one order for every layout (next game day, latest results, standings,
leaders); per-layout order is stage 6.

Every layout starts with `{% include core/context.html %}`, which assigns `league`, `active`, `season`
(the page's season, or the active one) and `stats` (that season's computed files). Includes read those
and their parameters, never `site.data` directly, so a part can be pointed at any season.

### 5.2 Includes: one per stage 3 part

| Include | Part (docs/design.md) | Parameters |
|---|---|---|
| `shell/head.html` | head: meta, noindex, CSS, pre-paint script | page |
| `shell/header.html` | header, brand badge or logo, nav, theme button | current nav key |
| `shell/ticker.html` | ticker (rendered when `league.layout == "scoreboard"`) | the latest results day |
| `shell/footer.html` | footer | none |
| `shell/sample-banner.html` | sample banner (new, 5.6) | none |
| `shell/page-title.html` | page title block | back, eyebrow, title, sub |
| `shell/section-head.html` | section heading | title, aside, aside_url |
| `parts/chip.html` | `.st-chip` (`st-team--N` or `--custom` with `--st-team-hex`) | team, size |
| `parts/result-card.html` | result card, rows or `--lines`, `--tie` | game |
| `parts/result-hero.html` | hero card (Scoreboard) | game |
| `parts/final-panel.html` | final panel (with the line score inside or after, per layout) | game |
| `parts/line-score.html` | line score, four shapes, `--card` / `--full`, scroll box | line_score, size, region |
| `parts/legend.html` | legend | items, stack, full |
| `parts/standings.html` | standings table, or the race on Scoreboard Home | standings, mode |
| `parts/leader-tile.html` | leader tile and grid | board |
| `parts/leader-list.html` | leader rows, the leaders table, Scoreboard boards | board |
| `parts/game-row.html` | game row | row, tag, show_time |
| `parts/next-game.html` | next-game panel | day |
| `parts/team-card.html` | team card | team |
| `parts/stat-table.html` | game-page `st-table--box` and plain stat tables | block |
| `parts/blocks.html` | dispatches `blocks[]` by `type` to the part includes | blocks |

Where a specimen branches on the **layout**, the include branches on `league.layout` the same way (the
race, the curling-grouped next-game rows, Classic's card foot). Where a specimen branches on the
**sport**, the branch becomes data from `present` or a `sport.yml` display hint (3.2); an include never
tests the sport id. Stage 4 ports every specimen part except `event-log`, `roster` and the sport game
tables, which arrive with hockey, curling and each sport in stage 5.

### 5.3 Head, theme, JavaScript

```html
<html lang="en" data-layout="classic" data-league-colour style="--st-league-color:#1F5FA8">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Schedule · Example Valley Stub League</title>
  <meta name="robots" content="noindex, nofollow">            <!-- unless search_engines -->
  <script>document.documentElement.classList.add("js");try{var t=localStorage.getItem("st-theme");
    if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>
  <link rel="stylesheet" href="…/assets/css/fonts.css">       <!-- then tokens, layouts/<layout>, base,
                                                                   parts-shell, parts-scores, parts-data, fallbacks -->
  <link rel="icon" href="…">                                  <!-- the logo, or href="data:," -->
  <script src="…/assets/js/site.js" defer></script>
</head>
<body class="st-page">
```
`data-league-colour` and the inline style appear only when `colour` is set (`--st-league-color-dark` too
with `colour_dark`). The theme button is rendered with the `hidden` attribute; `site.js` (about 40 lines)
un-hides it, shows the moon or sun for the page's current theme, sets `aria-label` to "Switch to dark
theme" / "Switch to light theme" (no `aria-pressed`, decision 11 of stage 3), sets `data-theme` and
stores `st-theme`. No other JavaScript in stage 4: no table sorting (stage 5 adds it if a sport's Stats
page needs it). Every path goes through `relative_url`; there are no external requests (fonts are
self-hosted; the only off-site links are the scorers-table credit and the league's contact).

### 5.4 Keeping includes and specimens in step

`scripts/design_system/contract.py` converts the stage 3 sample leagues (`sample.LEAGUES`) into the
computed-JSON shapes of 4.1. `tests/test_parity.py` then, for every (part, layout, sport) the design-system
page shows: renders the specimen function in Python; renders the include in a throwaway Jekyll site (the
repo's `_includes/` copied next to one generated page per case and the converted data); and compares the
two after normalising (tag tree, class sets, `role`, `aria-*`, `scope`, `tabindex`, text with collapsed
whitespace; `href` values, `id`s and the `hidden` attribute ignored). Any difference fails with the part,
layout, sport and the first differing node. It also proves the JSON contract can express every mockup
for all four sports before stage 5 writes a line of sport code.

The specimens stay the reference in stage 4. Rendering the design-system page from the includes and
retiring the specimens is a later option (10, question 6).

### 5.5 Pages and the empty states

Every list has a one-sentence empty state (no teams, no games yet, no players, season over), so the
empty real season renders. A team page shows roster, results, upcoming games and calendar links; a
player page shows totals as leader tiles and a game log as a `stat_table`.

### 5.6 New CSS in stage 4

Only what pages need and stage 3 lacks: `.st-banner` (the sample notice) and `.st-skip-link`, both on
existing roles (a pair `check_contrast.py` does not measure yet is added to its `PAIRS`), each with a
specimen on the design-system page. Archive rows and calendar links reuse `.st-list`, `.st-card` and
`.st-button--quiet`. Anything else a page seems to need is a question for review, not a one-off rule.

## 6. CI: `.github/workflows/build.yml`

Runs on pull requests, pushes to `main`, a nightly schedule (next game day, calendars) and by hand.

| # | Step | Notes |
|---|---|---|
| 1 | checkout; Python 3.12 (pip cache); Ruby 3.3 with `bundler-cache` | Ruby first: pytest runs Jekyll |
| 2 | `python -m pytest -q` | every test, including the Jekyll smoke and parity tests |
| 3 | `python scripts/check_contrast.py --check` | fails on any contrast failure or a stale `contrast.md` / `fallbacks.css` |
| 4 | `actions/configure-pages` (main only) | gives `origin` and `base_path` |
| 5 | `python scripts/build.py --site-url "$origin$base_path"` | data problems stop here, as annotations |
| 6 | `bundle exec jekyll build --baseurl "$base_path"` with a generated `_config.ci.yml` for `url` | Jekyll 4.4, `JEKYLL_ENV=production` |
| 7 | `scripts/build_preview.sh` | into `_site/preview/` |
| 8 | `scripts/check_links.sh` | html-proofer over `_site/`, the preview included, external links off |
| 9 | upload-pages-artifact, then a `deploy` job with `deploy-pages` | main only |

Pull requests run steps 1-3 and 5-8 with an empty base path and never deploy. The preview is built
before the link check so its links are checked too. **Differs from Masters:** the base path comes from
`configure-pages`, so a template copy publishes at `owner.github.io/<repo>/` (or a custom domain set in
the Pages settings) without editing `_config.yml`. No Node until stage 5.

## 7. Tests stage 4 ships

| File | Covers |
|---|---|
| `test_problems.py` | the Problem type, path prefixing, sorting, printing, `--json`, annotations, exit codes |
| `test_config.py` | `league.yml`: required keys, defaults, unknown keys with paths, layout ids, sport discovery (an unknown sport lists the folders), option types, placeholders, the colour gate (Gold stops with a `colour` message; Navy passes; `colour_dark` named in dark failures), logo missing |
| `test_loader.py` | seasons rules, teams, players ("First L.", numbers, same-name rule, spares), schedule (columns, dates, placeholders only on playoff rows, twice a day, cancelled with a file, `moved_from`), the envelope (each check with its path), drafts never opened, an empty current season |
| `test_standings.py` | each points rule (2-1-0, 3-1-0, the Masters period rule, OT loss), forfeits fixed and `per_period`, ties not allowed, playoff ties, each tiebreaker incl. the `head_to_head` skip and a capped `diff`, three-way ties without restart, shared ranks, the tiebreak note |
| `test_sport_contract.py` | every `sports/*/`: `sport.yml` valid, the four functions present, the sample season passes every check and is identical on two runs, every `at` path resolves to a node (or the missing key's parent) in its file, `present` uses only known block types and cell flags |
| `test_stub_sport.py` | every row of the 3.7 table, `read`, `present`, `derive` |
| `test_build.py` | the sample switch, `as_of` and next/latest day, archive listing, unique game ids, stub pages (which seasons, wiped each run), atomic write (nothing written on a problem), `--check` |
| `test_calendars.py` | per-team and league files, stable UIDs, UTC times across a DST change, cancelled games, placeholder playoff rows |
| `test_golden.py` | `build.py --sample --today` on the stub sample against `tests/golden/` (`UPDATE_GOLDEN=1` rewrites it) |
| `test_jekyll.py` | smoke: builds the stub sample site; every nav page and one of each stub page exist; `data-layout`, CSS order, noindex on and off, the colour attribute on and off, the toggle `hidden`, no external `src`/`href` |
| `test_parity.py` | 5.4 |

Jekyll tests are marked `jekyll` and skip locally without `bundle`; CI always runs them. **Not tested
yet:** real sports and shared fixtures (5), JS behaviour, six-layout screenshots (6), the entry page (7),
automated accessibility (axe), desktop (9). Screenshots at 390 px, both themes, are taken by hand.

## 8. Work packages

Package 1 goes first (small, it fixes the shapes); 2, 3, 4 and 6 then run in parallel (2's last check
needs 3's loader); 5 joins them; 7 and 8 finish. No two packages edit the same file.

| # | Package | Owns | Delivers / acceptance | Size | Review |
|---|---|---|---|---|---|
| 1 | Contract and config | `scripts/core/{types,problems,fmt,sports,config}.py`, `league.yml`, `tests/conftest.py`, `test_problems.py`, `test_config.py` | the types of 3.1, `sport.yml` schema validation, `league.yml` loading with defaults, placeholders and the colour gate; tests green | M | **Opus** (the interface) |
| 2 | Stub sport and samples | `sports/stub/`, `scripts/make_sample.py`, `data/` (seasons.yml, the three folders), `test_stub_sport.py`, `test_sport_contract.py` | 3.6-3.7; `make_sample.py` writes a season that passes the loader | M | |
| 3 | Loader | `scripts/core/loader.py`, `tests/fixtures/data/`, `test_loader.py` | 2.2-2.4 checks with paths, `sport.check`/`read` calls | M | |
| 4 | Standings engine | `scripts/core/standings.py`, `test_standings.py` | 3.5 as pure functions over results | M | **Opus** (rule mistakes) |
| 5 | Compute, write, build | `scripts/core/{compute,calendars,writer}.py`, `scripts/build.py`, `test_build.py`, `test_calendars.py`, `test_golden.py`, `tests/golden/` | section 4; golden files reviewed by eye once | L | |
| 6 | Parts | `_includes/parts/`, `_includes/shell/` (not head), `scripts/design_system/contract.py`, `tests/parity/`, `test_parity.py`, `parts-shell.css`, `specimens_shell.py`, the new `PAIRS` in `check_contrast.py`, `docs/design.md` | 5.2, 5.4, 5.6; parity green for every case; `check_contrast.py` passes | L | |
| 7 | Pages and site | `_config.yml`, `_layouts/`, `_includes/core/`, `_includes/shell/head.html`, the pages, `assets/js/site.js`, `Gemfile(.lock)`, `test_jekyll.py` | 5.1, 5.3, 5.5; smoke test green; screenshots of every page at 390 px light and dark | M | |
| 8 | CI and docs | `.github/workflows/build.yml`, `build_preview.sh`, `check_links.sh`, `requirements.txt`, `.gitignore`, `docs/data.md` (the data files, for the volunteer), `docs/sports.md` (section 3, kept true), README, CLAUDE.md, PLAN.md status | section 6; a green run on the pull request | S | |

Package 6 needs only this spec's JSON shapes and the stage 3 sample data, so it does not wait for the
build. The whole stage ends in one pull request, reviewed by Opus before it goes to the owner.

## 9. Out of scope for stage 4

Real sports and their fixtures, docs, JS ports and default rules (stage 5); the event log, roster,
numbers, facts and top-performer parts (stage 5, with their sports); per-layout page arrangement, logo
and scene checks, and the screenshot sweep across six layouts (stage 6; stage 4 only lets `layout:` pick
a stylesheet and ports the specimens' layout branches); the entry page and drafts handling (7); the setup
guide and the template flag (8); desktop (9); printable score sheets and the photo prompt (later); stats
table sorting; any analytics.

## 10. Decisions for the owner

Each has my recommendation; the build follows it unless you say otherwise.

| # | Decision | Recommended | Alternative | Consequence of the recommendation |
|---|---|---|---|---|
| 1 | Game file shape (2.4) | envelope + one `sheet:` block, sides `home`/`away` | Masters shape: boxes at the top level, keyed by team id | paths gain `sheet.`; Masters files need a small converter when stage 5 checks basketball against the real league |
| 2 | How sports show their data (3.4) | data blocks from a closed list, rendered by core includes | each sport ships its own Liquid | stage 5 adds about six shared parts; every sport stays inside the design system |
| 3 | "League decides" settings left unset (2.1) | build with the default and a visible `[placeholder]` | refuse to build until set | a new league sees its whole site at once, plus a "Still to decide" list in every build |
| 4 | Rules per season (2.2) | `overrides` in `seasons.yml` | one rule set for all seasons | archived seasons keep their own rules |
| 5 | Next game day (4.3) | by date, nightly rebuild, `as_of` for samples | Masters: first unplayed day | right on game day even when a sheet is late; builds depend on the date (tests pin it) |
| 6 | Markup reference (5.4) | specimens stay, guarded by the parity test | stage 6 renders the design-system page from the includes and drops the specimens | two copies of the markup until then, kept equal by a test |
| 7 | Tiebreakers (3.5) | in order, no restart; still level = shared rank | restart per smaller group, or order by name | explainable in one sentence under the table |
| 8 | Hosting (6) | base path from `configure-pages`, no `_config.yml` edit | the setup person edits `url`/`baseurl` | Pages must be enabled before the first deploy (a setup-guide step) |

## Riskiest assumptions

The biggest bet is that one generic line score, one stat table and a short list of block types can carry
four sports. The parity test against all four sample leagues checks the display side early, but hockey's
event log and curling's lineups have only been drawn, never computed, so stage 5 may need parts this
spec does not list. Second, standings come only from final and period scores; a league rule built on
anything else (curling ends won, a slo-pitch mercy result) needs a new tiebreaker or result kind in the
core. Third, the parity test runs a throwaway Jekyll build inside pytest: the suite needs Ruby and may be
slow (fallback: its own CI step). Fourth, `configure-pages` and the nightly rebuild tie the template to
GitHub Pages through Actions, which is the plan. Last, `as_of` keeps sample seasons mid-season but with
dates that age; the setup guide should say so.
