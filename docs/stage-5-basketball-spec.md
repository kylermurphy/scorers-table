# Stage 5, part 1: basketball

Status: **draft for the owner's review**, amended with the owner's answers (decisions 1, 2, 5 and 7 are decided;
section 7, sport previews, is new at the owner's request). Nothing is built yet. Section 10 lists the decisions:
until an open one is answered, the build follows the recommendation. Basketball is a port of the Masters site (`tb-masters-basketball/website`), so wherever this
spec says "as Masters", the Masters code is the reference and a test compares the two (section 8).

Read first: `BRIEF.md` (basketball's typical club rules), `docs/stage-4-spec.md` section 3 (the sport
interface), `docs/sports.md` (what the code does today).

---

## 1. Scope

**In this pull request**

| What | Where |
|---|---|
| The basketball sport folder | `sports/basketball/`: `sport.yml`, `rules.py` (`check`, `read`, `present`, `derive`), `sample.py`, `README.md` (the game file box by box, for the volunteer) |
| Shared test files | `sports/basketball/fixtures/`: one game per case, with the expected problems and numbers (section 8) |
| A converter for Masters files | `sports/basketball/convert_masters.py`: a Masters data folder in, a scorers-table data folder out (section 2.4) |
| Four small core extensions | the top performer part, ranking rates before rounding, four leaderboard keys, column lists for the stats pages (section 5) |
| Sample seasons | two made-up basketball seasons, golden files per sport (section 6) |
| Sport previews (owner request) | a `league.yml` setting that also publishes a made-up demo league of every sport at `/<sport>/` (section 7) |
| Docs | `docs/sports.md` (new keys and block), `docs/open-questions.md` (basketball's placeholders), `PLAN.md` status |

**Not in this pull request**

- The JavaScript copy of the rules and the entry page: stage 7. The shared fixtures are written now so the
  port can be checked against them (decision 8).
- Reading a photo (the `/record-game` helper and the copy-paste prompt): later. `/record-game` is tuned to one
  printed sheet and stays with Masters (`BRIEF.md`).
- The printable score sheet (`scoresheet.py`, form MBL-SS6): later. The rules here do not read a sheet spec yet.
- Curling, hockey, slo-pitch: their own pull requests. Core features only they need are listed as deferred in
  section 5.
- Six layouts per sport and the screenshot sweep: stage 6. This PR screenshots the basketball sample in the
  Basketball layout only.

## 2. The game file

### 2.1 Example

The Masters game file, with its boxes moved under `sheet:` and its team ids replaced by `home` / `away`.
Everything else is box for box what the Masters volunteer types today.

```yaml
game_id: 2026-11-05-1          # the core envelope (docs/data.md): unchanged for every sport
status: final
home: rapids
away: pines
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  players:                     # the roster rows, top to bottom: players.home.0 is row 1
    home:
      - {player: dave-m, num: 23, here: true, ft: MMXM, fouls: 2}
      - {player: greg-t, num: 11, here: true, ft: X}
      - {player: al-b, num: 5, here: false}
    away:
      - {player: mike-r, num: 7, here: true, ft: M, fouls: 3, tech: 1}
      - {player: jim-f, num: 12, here: true, ft: XM}
  running:                     # the running score: team total -> the scorer's jersey number
    home: {2: 23, 4: 11, 5: 23, 7: 23, 10: 11, 12: 23}
    away: {3: 7, 5: 12, 6: 12, 8: 7, 10: 7}
  lines:                       # the running total each end-of-quarter line is drawn under (Q1-Q4)
    home: [5, 7, 10, 12]
    away: [3, 6, 8, 10]
  boxes:                       # the score boxes under each roster, as written
    home: {q1: 5, q2: 7, q3: 10, q4: 12, ot: null, final: 12}
    away: {q1: 3, q2: 6, q3: 8, q4: 10, ot: null, final: 10}
  notes:                       # the Notes box: flagrant fouls, and anything else worth writing down
    - {side: away, num: 7, q: 3, kind: flagrant, text: elbow on a rebound}
```

A row may be `{num: 31, name: Jim K., here: true}` (a sub written in by hand, no player id yet) in a draft only.
A forfeit is the core's `forfeit: <team id>` with no `sheet`, as for every sport.

### 2.2 From Masters: kept, generalised, dropped

| Masters | scorers-table | |
|---|---|---|
| `game_id`, `status`, `home`, `away`, `scorekeeper`, `checked_by`, `review` | the core envelope, same keys | kept; the core checks them |
| `teams.<team id>.players` | `sheet.players.<side>` | kept, one level shorter, keyed by side |
| `running`, `lines`, `boxes` by team id | `sheet.running`, `sheet.lines`, `sheet.boxes` by side | kept, box for box |
| `notes: [{team, num, q, kind, text}]` | `sheet.notes: [{side, num, q, kind, text}]` | kept; `team` becomes `side` |
| `forfeit: <team id>` | `forfeit: <team id>` in the envelope | kept |
| row keys `player name num here ft fouls tech` | the same | kept |
| `form: MBL-SS6` | none | dropped: there is no printed sheet yet; its form id will live in the sheet spec, later |
| sheet limits from `spec.json`: 12 rows, 20 circles, 5 foul boxes, 2 T boxes, totals 1-175 | constants in `rules.py`: 15 rows, 20 circles, 2 T boxes, totals 1-250; foul boxes from the `foul_limit` option (default 5) | generalised: sanity limits until a printed sheet supplies its own |
| Q1-Q4 fixed | the number of quarters from `line_score.periods: 4`; box keys built from the period's short word (`q1`...) | generalised, so halves later is a words change, not a format change (decision 3) |
| a tie after Q4 must go to overtime (league rule 4) | the `overtime` option: `overtime` (default) or `none` | generalised (decision 2) |
| a tie after overtime stands (rule 4); a forfeit is 1-0 every quarter (rule 24); 1 point per quarter won + 3 per win | `league.yml` `standings:` (`ties`, `forfeit`, `period_points`, `points`) | generalised: Masters becomes a documented preset (section 3.4) |
| messages name team ids ("#77 scored for bb") and league rule numbers | messages name the team ("#77 scored for Pines") and no rule numbers | reworded; the box (path) and the level stay identical |
| timeouts, team fouls | not recorded | dropped (Masters never recorded them either) |
| Thunder Bay, St. Pat's, the badge, the Sleeping Giant, `/record-game`, the `/flagrant/` page, season high and game bars | none | dropped (the flagrant page: decision 5) |

**Why keep the running score as `total: jersey`.** It is the paper sheet, and the Masters volunteer, entry page and
fixtures all use it; a list of baskets would be tidier but would break mechanical conversion and stage 7's port.
One quirk carries over: YAML reads `27:` as a number and the JavaScript YAML reader as text `"27"`; the Masters JS
port already handles it, and the fixtures keep it covered.

### 2.3 Paths

Paths are relative to `sheet` in `check` (the core adds `sheet.`), counting rows and circles from 0 as Masters does.

| Path (after the core adds `sheet.`) | The box |
|---|---|
| `sheet.running.away.27` | the away team's running-score box at 27 |
| `sheet.players.home.3` (`.num`, `.player`, `.here`, `.fouls`, `.tech`) | the home team's 4th roster row and its parts |
| `sheet.players.home.3.ft.2` | that row's 3rd free-throw circle |
| `sheet.lines.away.1` | the away team's end-of-Q2 line |
| `sheet.boxes.home.final` (`q1`-`q4`, `ot`) | the home team's Final box |
| `sheet.notes.0` (`.side`, `.num`, `.q`, `.kind`) | the first entry in Notes |

### 2.4 The converter

`python sports/basketball/convert_masters.py --from <masters>/data --to <folder> [--photos]` writes a whole
scorers-table `data/` folder: `seasons.yml` (`gym` -> `venue`, `gym_address` -> `venue_address`, each season's
`ppg_min_games` and `ft_min_attempts` -> `overrides.stats.minimums`), `teams.yml` (`short` -> `code`,
`colour_slot` -> `slot`, the hex records dropped), `players.yml` (`display` -> `name`), `schedule.csv` (`gym` ->
`venue`), every game and draft (as 2.2; `review` paths mapped too), and photos with `--photos`. It prints the
`league.yml` lines of the Masters preset (3.4). It refuses to write into a folder that already has files.

A forfeit file's `notes` (e.g. "bb had three players at 9:55") have nowhere to go: a forfeit has no sheet, and the
envelope's `notes` are published on the game page, which Masters never did. The converter leaves them out and
prints each one, so nothing is published by accident.

Converted Masters data is **never committed** to scorers-table: the real season names real players, and the
Masters sample seasons use Thunder Bay place names (`CLAUDE.md`: sample data must not look real). Tests convert it
into a temporary folder (section 8).

## 3. The rules in Python

### 3.1 Checks

Every check of Masters `sheet_rules.check` that is about the sheet, at the same box. Header checks (`game_id`,
`status` and folder, `home`/`away` against the schedule, `review` left in a final file, `checked_by`, `forfeit`)
are the core's already. "Gap" means error in `games/`, warning in `drafts/` (the core rule for empty boxes).

| Check (path relative to `sheet`) | Level |
|---|---|
| a key other than `players running lines boxes notes` (`<key>`) | error |
| `players`, `running`, `boxes` missing or not `home` + `away` | gap |
| `players.<side>`: not a non-empty list; more than 15 rows; nobody ticked Here | error |
| `players.<side>.<i>`: not a row; an unknown key (`.<key>`) | error |
| `.num` not 0-99 or `"00"`; the same number on two rows of a side | error |
| `.player` missing (a `name` only: a sub not yet in `players.yml`) | gap |
| `.player` not in `players.yml`; listed twice in the game | error |
| `.player` on another team and not `sub: true` (new: the stub's check; Masters did not look) | warning |
| `.here` not true or false | error |
| `.ft` not made up of `M` and `X`; more than 20 circles (`.ft.20`) | error |
| `.fouls` not 0 to `foul_limit`; `.tech` not 0-2 | error |
| `.ft`: more made free throws than the player's scores in the running score | warning |
| `running.<side>.<total>`: not a box from 1 to 250; a jump that is not 1, 2 or 3; not a jersey number; a number on no row of that side; a scorer not ticked Here | error |
| `lines.<side>` missing | gap |
| `lines.<side>`: not four running totals; `.<q>` under a total with no box; a line above the one before | error |
| `boxes.<side>.q<n>`: not a count; not the total at its line; less than the box before | error |
| `boxes.<side>.final`: not a count; not the last running total | error |
| `boxes.<side>.q4` more than the Final box | error |
| `boxes.<side>.ot`: not the total after overtime; filled in with no overtime; filled in when `overtime: none` (new) | error |
| `boxes.home.q4`: overtime played but Q4 was not tied | error |
| `boxes.home.final`: tied after Q4 with no overtime, when `overtime: overtime` | error |
| `notes`: not a list; `.<n>` not an entry; an unknown key (new); `.kind` not `flagrant` or `note` | error |
| a flagrant's `.side` not `home`/`away`; `.num` on no row of that side; `.q` not 1-4 or `OT` | error |
| `players.<side>.<i>.fouls`: more flagrants in Notes than slashed foul boxes (a flagrant is also a personal foul) | error |

The core then adds, at `Score.final_at` (`sheet.boxes.<side>.final`): a tied playoff game, and a tied
regular-season game when `ties: false`. Masters reported both at the home Final box too.

`check` never raises and returns every problem, as the contract test demands; like Masters, it stops after a
problem that makes the later checks meaningless (no `running`, no `boxes`, a quarter box missing) rather than
reporting a cascade.

### 3.2 How the numbers come from the sheet (`read`)

| Number | From (as Masters) |
|---|---|
| Points | the running score: each jump from a side's previous total (1, 2 or 3) goes to the jersey number in the box |
| FTM, FTA | the circles: FTM = `M`s, FTA = `M`s + `X`s. Never the running score: under some league rules a free throw can be worth more than 1 |
| GP | `here: true` on a row with a player id. A row not ticked gets no line, so no game played |
| PF, T | `fouls`, `tech` |
| Flagrant | Notes entries with `kind: flagrant`, counted per row (side and number) |
| Quarter scores | the differences of the Q boxes (they hold running totals) |
| Overtime | played when the final is above a tied Q4, or (a scoreless overtime) both OT boxes are filled in; all overtime periods are one OT column, as the paper has one OT box |
| Final | the last running total (the Final box must agree) |

`read` returns `Score(final, periods = quarter points, extra = [final - q4] when overtime, decided_in = "overtime"
or "regulation", final_at = sheet.boxes.<side>.final)`, one `Line` per row ticked Here with counts `pts ftm fta pf
tech flagrant`, no team lines, and `facts = {"technicals": [...], "flagrants": [{side, player, num, q}]}` for the
game page. A flagrant's `text` is not passed on (decision 5).

### 3.3 Overtime, ties, forfeits

- `overtime: overtime` (default): a game level after Q4 must have OT boxes. Still level after overtime: a tie if
  the league allows ties (`ties: true`), otherwise the core reports it (keep playing until someone wins). A playoff
  game never ends tied.
- `overtime: none`: no OT boxes; a game level after Q4 is a tie, or an error with `ties: false`.
- An overtime win and loss are `ot_win` / `ot_loss` for the core; `points.ot_win` and `ot_loss` default to win and
  loss, so overtime changes nothing unless a league says so.
- A forfeit is the core's: no player gets a game played or any stat, as Masters.

### 3.4 Standings defaults, and the Masters preset

`sport.yml` holds `BRIEF.md`'s typical club rule. Each "league decides" setting is wrapped `{value, decide: true}`,
so the site shows `[placeholder]` and the build lists it under "Still to decide" until the league sets it.

```yaml
standings:
  rank_by: points
  points: {win: 2, tie: 1, loss: 0}                         # BRIEF: 2 points a win
  period_points: 0
  ties: {value: false, decide: true}                        # BRIEF: ties only if the league allows them
  forfeit: {value: {score: [20, 0]}, decide: true}          # decision 6
  tiebreakers: {value: [head_to_head, diff, points_for], decide: true}
  columns: [gp, w, l, pts, diff]                            # decision 1 (T added when a league allows ties)
```

**The Masters rule is a preset, not a sport option.** The core already expresses it. The README gives the lines to
paste into `league.yml`, and the converter prints them:

```yaml
rules: {overtime: overtime}
standings:
  points: {win: 3, tie: 0, loss: 0}
  period_points: 1                    # 1 per quarter won; a tied quarter gives nobody a point
  ties: true                          # a tie after overtime stands
  forfeit: {score: per_period}        # 1-0 in every quarter: 4-0, and 7 points to the winner
  tiebreakers: [head_to_head, diff]
  columns: [gp, w, l, t, pw, pts, diff]
```

Known differences from Masters, both from stage 4 decision 7 and visible only in rare ties: teams still level
after the last tiebreaker share a rank (Masters ordered them by name), and head-to-head is skipped unless every
pair of tied teams has met (Masters: unless each tied team has met at least one of the others).

## 4. Stats and pages

### 4.1 Player stats

Counting stats (group `player`): `pts` PTS, `ftm` FTM, `fta` FTA, `pf` PF, `tech` T, `flagrant` FLG. Rates from
`derive`: `ppg` PPG (points / GP) and `ft_pct` FT% (100 × FTM / FTA, `None` with no attempts), one decimal, half
up. `derive` returns the unrounded value; the core rounds for display and ranks on the exact value (E2). FT% shows
as `90.0` (the `%` is in the column label and the tile's label), as on Masters and the design canvas, so no
`format:` option is needed yet.

| Page | Columns (in this order) | As Masters |
|---|---|---|
| Stats table (everyone) | GP PTS PPG FTM FTA FT% | yes |
| Player: season totals | GP PTS PPG FTM FTA FT% T (Season row, Playoffs row) | Masters showed T as a tile |
| Player: game log | PTS FTM FTA T | Masters showed a "Tech" badge |

The table and player pages are core; the column lists are E4. Playoff stats stay apart, as Masters.

### 4.2 Leaderboards and minimums

| Board | Stat | Tile | Minimum | Notes |
|---|---|---|---|---|
| Points / game | `ppg` | yes, hot edge | `ppg_min_games` games, never more than the team has played (default 0, `[placeholder]`) | as Masters |
| Free throw % | `ft_pct` | yes, accent edge | `ft_min_attempts` attempts (default 10, `[placeholder]`) | a qualified 0.0% shooter is ranked (`zero: true`, E3), as Masters |
| Points | `pts` | no | none | |
| Technical fouls | `tech` | no | none | playoffs included (`playoffs: true`), Stats page only (`home: false`), not in a player's "Ranks" line (`player_rank: false`); decision 5 |

The two tiles match the design canvas (PPG, FT%). Masters breaks a tie in exact PPG by points, then name; the core
lists equal values by name. Ranks are the same; only the order inside a shared rank can differ.

### 4.3 Team columns

None beyond the core's standings columns (section 3.4). PF and PA in standings mean points for and against; the
box score's PF means personal fouls and its footnote says so (as the canvas does).

### 4.4 The game page (`present`)

| Block | Part | Content |
|---|---|---|
| line score | core `line_score`, shape `quarters` | Q1-Q4, plus an OT column when there was overtime; each team's biggest quarter marked (`won` flag, legend "Biggest quarter for each team", as the approved mockup; every quarter equal to the biggest is marked) |
| result card | core `card` | note "Top: #23 Dave M. 24 pts"; `note_long` "Top scorer: #23 Dave M. 24 pts, 6-7 FT" for Scoreboard's game of the week |
| hero tiles | core (`tiles: None`, from the line score) | |
| top performer | **new core part** `top_performer` (E1) | label "Top scorer", the player, "Rapids · 6-7 free throws", 24 POINTS. Two players tied: two tiles; three or more: no tile (the card note says "3 players with 12 pts") |
| box score, home and away | core `stat_table` | # · Player · PTS · FTM-FTA · PF, players ticked Here in sheet order, totals row "Team · 8 played", note "Free throws 65.0%" (none with no attempts) |
| fouls note | core `note` | only when there were any: "Technical fouls: #7 Mike R. (Pines). Flagrant fouls: #7 Mike R. (Pines), Q3." Never the Notes box text (decision 5) |
| footnote | core `note` | "PF = personal fouls. Points come from the running score on the score sheet; free throws from its circles." |

Everything except the top performer exists in the core today and is already covered by the parity fragment
`game-tables-box`.

## 5. Core extensions

Checked against the code (`scripts/core/compute_stats.py`, `sports.py`, `model.py`, `tests/parity/cases.py`).
Each is small, generic and tested on its own; none tests the sport id.

| # | Extension | Needed now because | Files | Test |
|---|---|---|---|---|
| E1 | **`top_performer` block**: `{type, label, player, side, value, unit, detail}` | the game page in the approved mockup | `model.py` (`BLOCK_TYPES`); new `_includes/parts/top-performer.html`; `parts/blocks.html` (dispatch); `assets/css/parts-scores.css` (the name may be a `<span>` for a past season with no player pages: selector `.st-top-scorer__name`, the whole-tile overlay only on the link); `scripts/design_system/contract.py` (`_basketball_blocks` emits it first); `tests/parity/cases.py` (remove the `drop` of `div.st-top-scorer` from `game-tables-box`, update the `SKIPPED` reason); `docs/design.md`, `docs/sports.md` | the parity case now compares the tile in every layout that shows basketball tables; Jekyll smoke: an archive game renders a `<span>`. The specimen and CSS exist already (`.st-top-scorer`); it uses only `text`, `muted` on `surface`, `accent` (large) and the `hot` edge, all measured by `check_contrast.py` today, which must still pass with `docs/contrast.md` unchanged |
| E2 | **Rank rates before rounding**: `derive` may return unrounded numbers; `totals` in the JSON are rounded to `places`; boards sort on the exact value | Masters ranks 20.14 above 20.06 though both show 20.1 | `compute_stats.py` (`_stat_block`, `_player_board`); `docs/sports.md` | unit: two players at 20.14 and 20.06 PPG get ranks 1 and 2; the stub (which rounds itself) is unchanged in the golden files |
| E3 | **Leaderboard keys**: `zero: true` (a value of 0 is ranked; `None` never is), `playoffs: true` (count playoff games too), `home: false` (Stats page only), `player_rank: false` (not in a player's Ranks line) | FT% (0.0% is a real result), technical fouls across the season, keeping the technical list off Home | `sports.py` (`_check_leaderboards`); `compute_stats.py`; `index.html` (filter boards with `home: false`); `_includes/core/stat-line.html` | `test_sports.py` (schema, typos); unit tests per key on a small season |
| E4 | **Column lists**: optional `stats.columns.<group>: {table, totals, log}`, each a list of stat keys in order; left out, today's order (GP, counting, rates) | Masters' order (PPG beside PTS) and leaving PF, T, FLG off the Stats table | `sports.py` (`_check_stats`: `columns` becomes a reserved name like `derived`, `team`); `compute_stats.py` (`leaders.columns[group]` becomes `{table, totals, log}`); `_includes/core/stat-line.html`, `game-log.html`, `player-table.html` | schema tests; the stub's pages are unchanged (golden JSON changes shape only, reviewed by eye) |

**Deferred, with the sport that needs them** (none is needed by basketball, and an option no sample uses would go
untested):

| Later | For | Why not now |
|---|---|---|
| leaderboard `order: asc` | hockey goals-against average (lower is better, 0.00 valid) | no basketball board ranks low-is-best |
| a `format:` for rates (`.333`, `.912`) | slo-pitch average, hockey save % | FT% shows as `90.0` with `places: 1` |
| period words chosen by an option | basketball halves | decision 3 |
| stats and boards shown only when an option is on | free throws not kept | decision 4 |

## 6. Sample data

`sports/basketball/sample.py`:

- `LEAGUE_NAME = "Riverside Masters Basketball"` (the made-up league of `BRIEF.md` and the design system).
- `TEAMS`: Rapids RAP, Herons HER, Foxes FOX, Pines PIN, Comets COM (the design system's). `PLAYERS_PER_TEAM = 8`.
- `sheet(rng, game, ctx)`: a port of Masters `build_sheet` and `_fill_quarters`: draw each player's points, free
  throws and fouls, choose quarter totals that honour the outcome, then fill the running score so every quarter ends
  on its box. As Masters, made free throws are written as 1-point scores (a simplification for made-up data). The
  outcome bends to the rules: `ot` with `overtime: none` becomes a tie; with overtime, a `tie` is a game level after
  overtime (make_sample asks for one only when ties are allowed). Over a season it writes a few technical fouls,
  one flagrant (with a matching foul box) and one overtime game.

`scripts/make_sample.py` already does the rest (players with a `00` and spares, round robin, a cancelled and a moved
game, a forfeit, playoff rows, one draft) and runs the loader on what it wrote; it needs no change. When
`ctx.folder` is `drafts`, `sheet()` adds a hand-written sub row (`name:` only, no player id), so the draft path of
the rules is in the sample.

Golden files become one folder per sport: `tests/golden/stub/` (today's files, moved) and `tests/golden/basketball/`.
`test_golden.py` is parametrised by sport: for each, it writes the sample into a temporary root (a `league.yml` with
that sport, `data/seasons.yml` from the repo), runs `build.py --sample --today 2026-11-20` there and compares.
`UPDATE_GOLDEN=1` rewrites both; the basketball standings and leaders are checked once by hand against the sample
files, as stage 4 did for the stub.

`league.yml` ships with `sport: basketball` (decision 7, decided), so the committed `data/sample-*` become the
basketball sample seasons and `docs/data.md`'s examples move to basketball. The stub stays the core's test sport,
with its own golden files.

## 7. Sport previews

The owner asked to "build previews of all pages", each sport at its own path: `basketball/`, later `curling/`,
`hockey/`, `slopitch/`. Each one is a full copy of the site, built from that sport's made-up sample league, as an
option of the normal build. This is also the "live demo for each sport" that `PLAN.md` puts in stage 8, made early
and made per sport, so it grows by itself as each stage 5 sport lands.

### 7.1 The setting

```yaml
preview: true            # unchanged: /preview/ = YOUR league (name, colours, logo, layout) with made-up games
sport_previews: false    # new: true = also /basketball/, /curling/ ... one made-up demo league per sport
                         #      or a list: [basketball, hockey]
```

| Value | Builds |
|---|---|
| `false` (the default when the key is left out) | nothing extra |
| `true` | one copy per sport folder that has a sample and is not marked `demo: false` (below) |
| a list of sport ids | those, in that order; an id that is not such a sport is an error naming the ones there are |

**Keep both settings, not merged.** They answer different questions. `/preview/` shows the league's own site with
made-up games ("what will our site look like?"); `/<sport>/` shows the template's sample league for a sport ("what
does scorers-table do for curling?"). Merging them into one key would make a league that wants one turn the other
on. **No migration:** `preview` keeps its meaning and default, and `sport_previews` is new and off unless set. The
template is not in use by any league yet, so nothing else changes.

**Which sports.** Every folder in `sports/` with a `sample.py`, except one whose `sport.yml` says `demo: false` (a
new optional key, default `true`). The stub says `demo: false`: it is a test sport, and nobody should see it as a
real one. The league's own sport is included too: `/basketball/` is the template's Riverside Masters Basketball in
the Basketball layout, which is not the same page as `/preview/` (the league's own name and look).

**What a sport preview shows.** The sport's `sample.py` league (`LEAGUE_NAME`, `TEAMS`), the sport's
`default_layout`, no league colour or logo, the sample seasons with their `as_of` dates, and the sport's own
defaults, so its "Still to decide" settings show as `[placeholder]`, which is what a new league would see. Nothing
from the league's `league.yml` reaches it except `timezone` and `time_format`. A future layout setting per preview
(say `/basketball/classic/`) is not part of this.

### 7.2 How the build makes N copies

Today `scripts/build_preview.sh` runs `build.py --sample`, builds Jekyll into `_site/preview/` with baseurl
`<BASE_PATH>/preview`, then runs `build.py` again so the working tree is left as it was. Sport previews use the same
steps, once per sport, in the same script (its name and CI step stay):

1. `python scripts/preview_root.py --list` prints the sport ids `sport_previews` asks for (and checks them).
2. For each id, `python scripts/preview_root.py <id> <tmp>` writes a temporary root: a `league.yml` (the sample's
   name, the sport, its default layout, `sample_data: true`, `preview: false`, `sport_previews: false`,
   `search_engines: false`), a `data/seasons.yml` with an empty current season and the two sample seasons, the
   sample data from `make_sample.py`'s generator (the same fixed seed, so the files are the ones the golden test
   checks), and a link to the repo's `sports/`.
3. `build.py --root <tmp> --out . --sport-preview <id>` writes `_data/computed/` and the stub pages into the Jekyll
   source, then `jekyll build --destination _site/<id>` with an overlay config: `baseurl: "<BASE_PATH>/<id>"`,
   `live_baseurl: "<BASE_PATH>"`.
4. After the last copy, the real build runs again (also when a step fails), exactly as today.

| Concern | How it is handled |
|---|---|
| Paths | every link already goes through `relative_url`, so a baseurl of `<BASE_PATH>/basketball` is all a copy needs. The layout's banner link to the live site reads the new `site.live_baseurl` instead of cutting `/preview` off the end of the baseurl (today's Liquid trick does not work for N copies; `/preview/` moves to the same overlay) |
| Clashes | a sport id may not be one of the site's own top-level paths (`archive assets calendar games players preview rules schedule sheets stats teams`); the build refuses with a message. None of the four sport ids clash |
| The banner | `build.py --sport-preview` sets `active.preview_kind: sport` and `active.sport_previews: [{id, name, url}]`. The banner says "Sport preview: a made-up basketball league, to show what the template does." with links to the other sport previews and "Go to the live site" |
| Search engines | always `noindex, nofollow`: the generated `league.yml` sets `search_engines: false`, whatever the league chose for its own pages |
| Calendars | none: a sport preview's current season is empty and `--sport-preview` writes no calendar files, so its pages show no subscribe links. Nothing can clash with the real site's `.ics` files or their event ids |
| Links to the previews | none from the league's own pages, as for `/preview/` today: a league's visitors should not land on a made-up league. Each preview's banner links to the others, `/preview/`'s banner lists them when they exist, and the README gives the addresses (open question 9) |
| Photos, entry page | none in a preview (`photos: false`; the entry page is stage 7 and will be left out of previews) |

### 7.3 Cost

Measured in this container (4 cores) on 16 October 2026:

| Build | Pages | Python | Jekyll | Size | Link check |
|---|---|---|---|---|---|
| scorers-table stub sample (23 games, 5 teams of 7) | 73 | 1.6 s (`build.py --sample`) | 5.6 s | 1.9 MB | 2.3 s (0.8 s of checking) |
| Masters basketball sample (28 games, 50 players), through the same Jekyll 4.4 | 94 | 0.6 s | 4.7 s | 3.3 MB | |

The scorers-table basketball sample does not exist yet (package 3), so its numbers are an estimate from these:
about 100-110 pages, 8-10 seconds a copy including the sample generator and its share of the link check, about
2.5 MB. With four sports that is roughly 40 seconds more per deploy and 10 MB more in the Pages upload (the limit is
1 GB). The copies run one after another because they share the Jekyll source folder; running them in parallel
would need a copy of the source per sport and is not worth it at this size. Package 6 records the real basketball
numbers in the pull request.

### 7.4 Tests

- `test_config.py`: `sport_previews` takes `false`, `true` and a list; an unknown id, a `demo: false` sport and a
  clashing id are errors with their paths.
- `test_sports.py`: the `demo` key; the stub has `demo: false`.
- `tests/test_preview_root.py`: the temporary root is the same on two runs, its `league.yml` loads with no problem,
  and its sample data equals what the golden test uses for that sport.
- `test_jekyll.py` (marked `jekyll`, always run in CI): with `sport_previews: [basketball]`, `build_preview.sh`
  makes `_site/basketball/`; every internal link and asset there starts with the copy's base path; every page has
  the noindex tag and the sport-preview banner with a working link back; no `.ics` file is under it; the real
  site's pages and `calendar/` are unchanged afterwards; the main site links nowhere into `/basketball/`.
- CI's existing link check already walks all of `_site/`, so every copy is link-checked on every pull request.

### 7.5 Who builds it

Package 6 (section 9), after package 1 (it edits `sports.py` too) and package 3 (it needs the basketball sample).

## 8. Tests

| Test | What |
|---|---|
| `sports/basketball/fixtures/` + `tests/test_basketball_fixtures.py` | the **shared fixtures**: `context.yml` (two teams, players, options) and per case `<name>.yml` (`fixture: {folder, game_type, options}` and `sheet:`) with `<name>.expected.json` (`problems`: level, at, message, in order; `reading`: score, lines, facts, or `null`). The runner compares `check` and `read` exactly; `UPDATE_FIXTURES=1` rewrites the expected files for review. Stage 7's Node runner reads the same files |
| fixture cases | the ten Masters sheet cases converted (`clean`, `and-one`, `bad-final`, `draft-with-sub`, `ft-mismatch`, `overtime`, `page-two`, `tie`, `tie-without-overtime`, `unknown-jersey`; Masters' `forfeit` case becomes a loader test, as forfeits are the core's), plus one case per row of 3.1 they miss (about 20: jump of 4, scorer not Here, number on two rows, lines going down, a Q box off its line, OT box without overtime, OT with `overtime: none`, more flagrants than fouls, a sub's `name` in a final file, unknown keys, a scoreless overtime, 15+ rows, `.ft.20`...). Masters' made-up names (Alpha, Bravo, `al-a`) are kept: they are fixtures, not a league |
| `tests/test_basketball_sport.py` | `present` (line score marks, OT column, top performer with 1, 2 and 3 tied scorers, box score totals and FT% note, the fouls note), `derive` (no attempts, rounding half up), `sample.sheet` honours every outcome under both `overtime` values |
| `tests/test_sport_contract.py` | unchanged; picks up the new folder by itself (mutated sheets, paths resolve, drafts never stricter, sample identical on two runs) |
| `tests/test_basketball_convert.py` (offline, in CI) | the converter on small Masters-shaped files written inside the test: every key mapping of 2.2, review paths, forfeit notes left out and printed, refusing a non-empty folder |
| `tests/test_masters_parity.py` (local only) | runs when `MASTERS_SITE` points at a checkout of `tb-masters-basketball/website`, skipped otherwise and never in CI (the Masters repo is a reference, not a dependency). (1) Converts each Masters fixture and checks our problems have the same levels at the mapped paths, and our numbers equal Masters' lines. (2) Runs Masters `build_stats.py --data <masters>/data --out <tmp>` and our converter + `build.py` on the same data with the preset, and compares per season: standings (GP W L T PTS PF PA QW, and the order where no name or head-to-head-skip tiebreak was used), every player's GP PTS FTM FTA PPG FT% techs flagrants, the three leaderboards (values and ranks, order inside a rank ignored), and every game's quarter scores and final. Known differences (3.4, 4.2, points leaders with 0 points) are listed in the test, not silenced. The Masters real season has no games yet (October 2026), so today this runs on its two sample seasons (28 games) and the fixtures; it gains real games as the season goes on |
| core tests | E1-E4 (section 5) in `test_sports.py`, `test_build.py`, `test_parity.py`, `test_jekyll.py` |

Nothing converted from Masters data is written outside the test's temporary folder.

## 9. Work packages

Packages 1, 2 and 4 start together; 3 needs 2 (and 1's schema keys); 6 needs 1 and 3; 5 finishes. Packages that
share a file (`sports.py`, `test_jekyll.py`, the golden files) never run at the same time.

| # | Package (Sonnet builds) | Owns | Done when |
|---|---|---|---|
| 1 | Core extensions E1-E4 | `scripts/core/{model,sports,compute_stats}.py`, `_includes/parts/{top-performer,blocks}.html`, `_includes/core/{stat-line,game-log,player-table}.html`, `index.html`, `parts-scores.css`, `scripts/design_system/contract.py`, `tests/parity/cases.py`, `tests/test_{sports,build,parity,jekyll}.py`, stub golden regenerated | tests green, parity green with the drop removed, `check_contrast.py` passes with `docs/contrast.md` unchanged, the stub's pages unchanged |
| 2 | Basketball rules | `sports/basketball/{sport.yml,rules.py,README.md}`, `sports/basketball/fixtures/`, `tests/test_basketball_{fixtures,sport}.py` | every row of 3.1 has a fixture; the contract test passes; the README lists every check with its path and level, the Masters preset, and the volunteer's how-tos (overtime, a tie, a sub, a flagrant) |
| 3 | Sample and golden | `sports/basketball/sample.py`, `tests/test_golden.py`, `tests/golden/<sport>/`, `league.yml` (`sport: basketball`) and `data/sample-*` | `make_sample.py --check` clean; golden files reviewed by eye; screenshots of Home, Schedule, a game, Stats and a player at 390 px, light and dark, Basketball layout |
| 4 | Masters converter | `sports/basketball/convert_masters.py`, `tests/test_basketball_convert.py`, `tests/test_masters_parity.py` | offline tests green; the parity test run locally against a Masters checkout, its output pasted into the pull request |
| 6 | Sport previews (section 7) | `scripts/preview_root.py` (new), `scripts/build_preview.sh`, `scripts/build.py` (`--sport-preview`), `scripts/core/{config,compute}.py` (the setting, `active.json`), `scripts/core/sports.py` (`demo`), `sports/stub/sport.yml` (`demo: false`), `_layouts/default.html` (`live_baseurl`), `_includes/shell/sample-banner.html`, `league.yml` (the key, with a comment), `tests/test_{config,sports,preview_root,jekyll}.py`, golden `active.json` | tests green; a CI run that publishes `/basketball/` beside the real site and passes the link check; the measured time and size per copy in the pull request; screenshots of `/basketball/` Home at 390 px, light and dark |
| 5 | Docs | `docs/sports.md`, `docs/data.md` (examples become basketball; `sport_previews` beside `preview`), `docs/open-questions.md`, `README.md` (the preview addresses), `CLAUDE.md`, `PLAN.md` (stage 8's per-sport demo now exists) | the docs say what the code does |

**Opus reviews:** package 1's interface before 2 and 3 use it; package 2 line by line against Masters
`sheet_rules.py` (every check, every path, every level, overtime and tie handling); the Masters parity run and every
listed difference; the basketball golden standings and leaders by hand; package 6's base paths, banner and
restore-on-failure. Then the whole pull request, before it goes to the owner.

## 10. Decisions for the owner

Decisions 1, 2, 5 and 7 were decided by the owner (October 2026). Decisions 3, 4, 6 and 8 are recommended and
await the owner's confirmation; the build follows the recommendation until then. Question 9 is new.

1. **Default standings. DECIDED:** 2 points a win, ranked by points, columns GP W L PTS DIFF (the README tells a
   league that allows ties to add T). The Masters rule (1 per quarter won, 3 per win) is a README preset, not a
   sport option. Not chosen: the mockup's W L PCT GB DIFF by win %.
2. **Ties and overtime. DECIDED:** overtime when level after Q4 (`rules.overtime`) and no ties
   (`standings.ties: false`), both shown as `[placeholder]` until the league sets them. A Masters-style league sets
   `ties: true`; a gym with a hard stop sets `overtime: none`.
3. **Quarters or halves.** Recommended and confirmed by the owner (October 2026): quarters only for now. The Masters sheet itself
   had halves until October 2026 (form MBL-SS5), so some leagues will want them; supporting them needs period
   words chosen by an option (a core change). The format is ready for it (box keys come from the period word).
4. **Free-throw stats optional.** Recommended and confirmed by the owner (October 2026): always kept for now. A league that
   never fills in the circles sees 0-0 and "—" in the FT columns and an empty FT% board, which is honest but
   cluttered; hiding them needs stats that depend on an option (a core change), best made when a league asks.
5. **Fouls on the site. DECIDED:** personal fouls only in the game box score. Technical fouls count the whole
   season, playoffs included (player page and a "Technical fouls" list at the foot of Stats). Flagrant fouls are
   named on the game page with their quarter, never the Notes text, and there is no `/flagrant/` page.
6. **Default forfeit score.** Recommended and confirmed by the owner (October 2026): 20-0 (FIBA's rule), shown as
   `[placeholder]`. A big margin moves the point differential, which is a tiebreaker; 2-0 or Masters' 1-0 per
   quarter barely does. A league can also cap the differential (`{diff: {cap: 15}}`).
7. **Which sport the template shows out of the box. DECIDED:** basketball. `league.yml` ships with
   `sport: basketball`, the committed sample seasons become basketball, and the stub stays the core's test sport
   with its own golden files. The owner also asked for a preview of every sport: section 7.
8. **JavaScript timing.** Recommended and confirmed by the owner (October 2026): `PLAN.md` says each stage 5 pull request has the
   rules in Python and JavaScript; the JavaScript copy moves to stage 7 with the entry page, its only user, and this
   PR commits the shared fixtures it will be tested against. Doing it now means porting before the entry page's
   design (stage 7, Opus) exists.
9. **Sport previews in the shipped template. DECIDED (October 2026):** the template's `league.yml` ships with
   `sport_previews: true`, so the template's own site is the per-sport demo; the setting's default is `false`, and
   the stage 8 setup guide lists it beside `preview` as something a league may turn off. The trade-off: a league
   that never reads that line publishes unlinked, noindex demo leagues at `/basketball/` and so on, and its deploys
   take about 40 seconds longer once all four sports exist. Linking the previews from a league's own pages stays
   off either way.

## Risks

- **Core changes inside a sport PR.** E1-E4 touch shared code and the stub's golden JSON. Package 1 goes first and
  gets its own Opus review so the sport packages build on a fixed interface.
- **The Masters comparison runs only by hand.** CI cannot see the Masters repo, so drift is caught only when
  someone runs `test_masters_parity.py`. The committed fixtures carry the rules; the comparison covers the
  arithmetic. Running it once per stage 5 sport PR that touches the core is a cheap habit.
- **The contract test's mutation pass on large sheets.** A basketball sheet has a hundred or more boxes, and the
  test mutates each six ways for every sample sheet and option. If it gets slow, it samples a few sheets per
  season (a test change, not a rules change).
- **Sport previews rewrite the working tree.** Like `/preview/` today, each copy writes `_data/computed/` and the
  stub pages into the Jekyll source and the script restores the real build afterwards. Four copies mean four
  chances to leave a local checkout showing a made-up league if the restore step breaks; the Jekyll test checks
  the restore, and the generated files are git-ignored, so nothing wrong can be committed.
