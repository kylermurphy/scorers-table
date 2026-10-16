# Basketball

Four quarters, a running-score sheet (each basket's scorer by jersey number), free-throw circles and fouls. The
game file is a box-for-box copy of that paper sheet: you copy what is written, and the site works out the points,
the free throws, the fouls and the standings. If a box does not add up, the check names it and **nothing is
published**.

This page is for whoever types the game files. How the files fit into a season is in `docs/data.md`; this page
is the `sheet:` part. The checks live in `rules.py`; `fixtures/` holds one game for every check below, and the
JavaScript copy of the rules (for the entry page) is tested against the same files.

- [The game file](#the-game-file)
- [The boxes](#the-boxes)
- [How the numbers come from it](#how-the-numbers-come-from-it)
- [What is checked](#what-is-checked)
- [How to](#how-to): overtime, a tie, a sub, a flagrant or technical foul, a forfeit
- [Settings the league may change](#settings-the-league-may-change)
- [The Masters preset](#the-masters-preset)
- [What the site shows](#what-the-site-shows)

## The game file

The top part is the same for every sport (`game_id`, `status`, `home`, `away`, `scorekeeper`, `checked_by`: see
`docs/data.md`). The sport's part is `sheet:`. Sides are always `home` and `away`, never team ids.

```yaml
game_id: 2026-11-05-1
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
  running:                     # the running score: the team's new total -> the scorer's jersey number
    home: {2: 23, 4: 11, 5: 23, 7: 23, 10: 11, 12: 23}
    away: {3: 7, 5: 12, 6: 12, 8: 7, 10: 7}
  lines:                       # the running total each end-of-quarter line is drawn under (Q1 to Q4)
    home: [5, 7, 10, 12]
    away: [3, 6, 8, 10]
  boxes:                       # the score boxes under each roster, as written
    home: {q1: 5, q2: 7, q3: 10, q4: 12, ot: null, final: 12}
    away: {q1: 3, q2: 6, q3: 8, q4: 10, ot: null, final: 10}
  notes:                       # the Notes box: flagrant fouls, and anything else worth writing down
    - {side: away, num: 7, q: 3, kind: flagrant, text: elbow on a rebound}
```

A forfeit has no `sheet` at all: see [A forfeit](#a-forfeit).

## The boxes

Rows, circles and quarters count from 0 in a problem's path, like list positions: `players.home.0` is the top
row, `ft.0` the first circle. A problem path always starts with `sheet.` in the message (`sheet.running.away.27`);
the paths below leave that off.

| Box | What goes in it |
|---|---|
| `players.<side>` | The roster rows, in order, up to 15. A row is `{player, num, here, ft, fouls, tech}`. |
| `players.<side>.<i>.player` | The player's id from `players.yml`. A sub written in by hand has `name: Jim K.` instead until they are added (a **draft** only). |
| `.num` | The jersey number in the # box, 0 to 99 (`"00"` in quotes). `0` and `"00"` are two different jerseys. Two rows of a side cannot share a number. |
| `.here` | The Here tick: `true` or `false`. Only players ticked Here get a game played and a line in the box score. |
| `.ft` | The free-throw circles in order: `M` filled (made), `X` slashed (missed), like `MMXM`. Up to 20. Leave it out for none. |
| `.fouls` | The slashed personal-foul boxes, 0 up to the league's foul limit (5 unless set). A flagrant foul counts here too. Leave it out for 0. |
| `.tech` | The slashed T boxes, 0 to 2. Leave it out for 0. |
| `running.<side>` | Every filled running-score box: `total: jersey number`. The totals run on past 100. |
| `lines.<side>` | The running total each end-of-quarter line was drawn under: `[Q1, Q2, Q3, Q4]`. Write 0 if a team had not scored. |
| `boxes.<side>` | `q1` to `q4` (the running total at the end of each quarter), `ot` (the total after overtime, or `null`) and `final`. |
| `notes` | The Notes box: `{side, num, q, kind, text}`. `kind` is `flagrant` or `note`; `q` is 1 to 4 or `OT`. |

## How the numbers come from it

| Number | From |
|---|---|
| Points | The running score: the jump from a team's previous total to each box (1, 2 or 3) goes to the jersey number in it. |
| FTM, FTA | The circles: FTM is the `M`s, FTA the `M`s and `X`s. Never the running score: a free throw can be worth more than 1 under some rules, so any jump might be one. |
| GP | `here: true` on a row with a player id. A row that is not ticked gets no line, so no game played. |
| PF, T | `fouls`, `tech`. |
| Flagrant fouls | The Notes entries with `kind: flagrant`, counted per player. |
| Quarter scores | The differences of the Q boxes (they hold running totals). |
| Overtime | Played when the final is above a tied Q4, or when both OT boxes are filled in (a scoreless overtime). However many overtime periods, the paper has one OT box, so there is one OT column. |
| Final score | The last running total (the Final box must agree). |

## What is checked

Every problem has a path (the box), a level, and one sentence that says what to do. An **error** stops the build.
A **warning** is shown and never stops it. A **gap** is an empty box: an error in `games/`, a warning in
`drafts/`, so a draft is never stricter than a finished file. Unknown lines are errors at every level, because they
are nearly always typos.

Rows marked *new* are not in the Masters rules the sport grew out of. After these, the core adds one more at
`boxes.home.final`: a tied playoff game, and a tied regular-season game when `standings.ties` is false (see
[A tie](#a-tie)).

| Path | What is wrong | Level |
|---|---|---|
| `<key>` | a line other than `players running lines boxes notes` | error |
| `players`, `running`, `boxes` | missing | gap |
| `players.<side>`, `running.<side>`, `boxes.<side>` | a side missing from the block | gap |
| `players.<side>` | not a non-empty list; more than 15 rows; nobody ticked Here | error |
| `players.zzz`, `running.zzz`, `lines.zzz`, `boxes.zzz` | a side that is not `home` or `away` (*new*) | error |
| `players.<side>.<i>` | not a row; an unknown key (`.<key>`) | error |
| `players.<side>.<i>.num` | not 0 to 99 or `"00"`; the same number on two rows of a side | error |
| `players.<side>.<i>.player` | missing (a row with only a `name`: a sub not yet in `players.yml`) | gap |
| `players.<side>.<i>.player` | not in `players.yml`; listed twice in the game | error |
| `players.<side>.<i>.player` | on another team and not `sub: true` in `players.yml` (*new*) | warning |
| `players.<side>.<i>.here` | not `true` or `false` | error |
| `players.<side>.<i>.ft` | not made up of `M` and `X` | error |
| `players.<side>.<i>.ft.20` | more than 20 circles | error |
| `players.<side>.<i>.fouls` | not 0 up to the foul limit | error |
| `players.<side>.<i>.tech` | not 0 to 2 | error |
| `players.<side>.<i>.ft` | more made free throws than the player has scores in the running score | warning |
| `players.<side>.<i>.fouls` | more flagrants in Notes than slashed foul boxes (a flagrant is also a personal foul) | error |
| `running.<side>` | not a block of `total: jersey number` | error |
| `running.<side>.<total>` | not a box from 1 to 250; a jump that is not 1, 2 or 3; not a jersey number; a number on no row of that side; a scorer not ticked Here | error |
| `lines` | missing | gap |
| `lines.<side>` | missing from a `lines` block | gap |
| `lines`, `lines.<side>` | `lines` not a block; not four running totals | error |
| `lines.<side>.<q>` | under a total with no box; above the line before it | error |
| `boxes.<side>` | not a block (*new*: with the box names it expects) | error |
| `boxes.<side>.<key>` | an unknown box (*new*): only `q1 q2 q3 q4 ot final` | error |
| `boxes.<side>.q<n>` | not a count; not the total at its line; less than the box before | error |
| `boxes.<side>.final` | not a count; not the last running total | error |
| `boxes.<side>.q4` | more than the Final box | error |
| `boxes.<side>.ot` | not the total after overtime; filled in with no overtime; filled in when the league plays no overtime (*new*) | error |
| `boxes.<side>.q4` | the league plays no overtime, but the running score ends above the Q4 box (*new*) | error |
| `boxes.home.q4` | overtime was played but Q4 was not tied | error |
| `boxes.home.final` | tied after Q4 with no overtime, when the league plays overtime | error |
| `notes` | not a list | error |
| `notes.<n>` | not an entry; an unknown key (`.<key>`, *new*); `.kind` not `flagrant` or `note` | error |
| `notes.<n>.side` | a flagrant's side is not `home` or `away` | error |
| `notes.<n>.num` | a flagrant's number is on no row of that side | error |
| `notes.<n>.q` | a flagrant's quarter is not 1 to 4 or `OT` | error |

When a box makes the later checks meaningless, checking stops there instead of listing a cascade: no rosters, no
running score, no score boxes, or a quarter box that is not a count.

The checks that look at the whole file (`game_id` against the file name and the schedule, `status` against the
folder, `home` and `away` against the schedule, `checked_by`, `review` left in a final file, `forfeit`) are the
core's: see `docs/data.md`.

## How to

### Overtime

If the score is level after Q4, the teams play overtime. Fill in the **OT box** for both teams with the team's
new running total (the same number as its Final box):

```yaml
boxes:
  home: {q1: 5, q2: 12, q3: 17, q4: 22, ot: 25, final: 25}
  away: {q1: 5, q2: 10, q3: 16, q4: 22, ot: 24, final: 24}
```

* However many overtime periods were played, the paper has one OT box and the file has one OT column.
* If nobody scored in overtime, write the Q4 total in both OT boxes (`ot: 22` for both at 22-22). That is how the
  file says overtime was played.
* If the game was not level after Q4, leave `ot: null`. An OT box on a game that did not go to overtime is an
  error, and so is a game that went to overtime with no OT box.
* A league that never plays overtime sets `rules: {overtime: none}` in `league.yml`. The OT boxes are then
  left empty, and a game level after Q4 is a tie (see below).

Whether the league plays overtime is the league's to decide. Until `rules.overtime` is set, the site shows
`[placeholder]` and plays overtime (the usual rule).

### A tie

* **Still level after overtime** (or level after Q4 where there is no overtime): the game is a tie only if the
  league allows ties (`standings: {ties: true}`). Write the file as it is. The standings show a tie.
* **Where ties are not allowed** (the setting the site starts with, shown as `[placeholder]` until the league
  decides), the check stops the build at `boxes.home.final` and says so. Check the Final and OT boxes against the
  paper sheet: a tied game should have been played on.
* A **playoff game never ends tied**; the check says so at the same box.
* Level after Q4 with the OT boxes empty, when the league plays overtime, is an error: the sheet is not
  finished (see [Overtime](#overtime)).

### A sub

A spare is anyone who is not on the team's roster that night.

1. Add them to `players.yml` first: `{id: jim-k, name: Jim K., team: null, sub: true}` (a spare who belongs to no
   team), with their number if they have one.
2. In the game file, give their row the id: `{player: jim-k, num: 31, here: true}`.

A regular player of another team who fills in is already in `players.yml`; mark them `sub: true` there, or the
check warns you (`... is not on <team>`). A warning never stops the build.

If you are typing the file before you know who the sub is, write the row as they wrote it on paper,
`{num: 31, name: Jim K., here: true}`, and save it as a **draft** (`drafts/`). The check warns that the row has no
player id yet. A finished file (`games/`) cannot have such a row: it is an error, because the points would have
nowhere to go.

### A flagrant foul, or a technical foul

* A **flagrant**: slash the foul box as usual (the row's `fouls` counts it, because a flagrant is also a personal
  foul) **and** write an entry in Notes with the player's side and number, and the quarter:

  ```yaml
  notes:
    - {side: away, num: 7, q: 3, kind: flagrant, text: elbow on a rebound}
  ```

  `q` is 1 to 4, or `OT`. The game page names the player with the quarter ("Flagrant fouls: #7 Mike R. (Pines),
  Q3"). **The `text` is for the file only; it is never shown on the site.** More flagrants for a player than
  slashed foul boxes is an error.
* A **technical**: slash the T box (`tech: 1` on the row; 0 to 2). Technical fouls count the whole season,
  playoffs included, and are listed at the foot of the Stats page and on the player's page.
* Anything else worth writing down goes in Notes as `{kind: note, text: ...}`.

### A forfeit

A forfeit has no sheet. The game file names the team that forfeited and leaves `sheet:` out:

```yaml
game_id: 2026-10-22-1
status: final
home: lynx
away: otters
checked_by: Lee M.
forfeit: otters
```

No player gets a game played or any stat. How the score counts (default: 20 to 0, shown as `[placeholder]`) is the
league's to decide under `standings: forfeit:` in `league.yml`.

## Settings the league may change

Set in `league.yml`; each one marked *decide* shows as `[placeholder]` on the site, and in the build's "Still to
decide" list, until the league sets it (even to the usual value).

| Setting | Values | Default |
|---|---|---|
| `rules.overtime` | `overtime`, `none` | `overtime` (*decide*) |
| `rules.foul_limit` | 1 to 9: the most personal fouls one player can have (the foul-out number) | 5 (*decide*) |
| `standings.points` | `{win, tie, loss, ot_win, ot_loss}` | 2, 1, 0 (an overtime win and loss count as a win and a loss) |
| `standings.ties` | `true`, `false` | `false` (*decide*) |
| `standings.forfeit` | `{score: [20, 0]}`, `{score: per_period}`, ... | `[20, 0]` (*decide*) |
| `standings.tiebreakers` | `head_to_head`, `diff`, `points_for`, ... | head-to-head, then point difference, then points for (*decide*) |
| `standings.period_points` | points for each quarter won | 0 |
| `standings.columns` | `gp w l t pw pts diff pf pa ...` | `gp w l pts diff` (add `t` when the league allows ties) |
| `stats.minimums.ppg_min_games` | games played before a player is ranked on points per game | 0 (*decide*) |
| `stats.minimums.ft_min_attempts` | free throw attempts before a player is ranked on free throw % | 10 (*decide*) |

Free-throw numbers are always kept: a league that does not fill in the circles sees 0-0 and dashes in the free
throw columns.

## The Masters preset

The Masters Basketball League's rule: one standings point for each **quarter won** and three for a win; a tie after
overtime stands; a forfeit counts as 1-0 in every quarter (four quarters and the win: 7 points); head-to-head, then
point difference. It is not an option of the sport; it is these lines in `league.yml`:

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

`pw` is the number of quarters won. Two differences from the Masters site, both from how the core ranks and both
visible only in rare ties: teams still level after the last tiebreaker share a rank (Masters listed them by name),
and head-to-head is skipped unless every pair of tied teams has met (Masters: unless each tied team had met at
least one of the others).

## What the site shows

* **Game page.** The line score (Q1 to Q4, and an OT column when there was overtime) with each team's biggest
  quarter marked; the final panel; the top scorer's tile (two players tied for the most: two tiles; three or
  more: none); a box score for each team (# · Player · PTS · FTM-FTA · PF, players ticked Here, a totals row
  and "Free throws 65.0%"); a note naming the technical and flagrant fouls, when there were any; and the
  footnote "PF = personal fouls...". Personal fouls are shown only here. (In the standings, PF and PA mean
  points for and against.)
* **Result card.** "Top: #23 Dave M. 24 pts".
* **Stats page.** GP, PTS, PPG, FTM, FTA and FT% for everyone, with the leaderboards for points per game, free
  throw %, points, and technical fouls. A player with 0.0% is ranked, if they have enough attempts.
* **Player page.** Season and playoff rows (GP PTS PPG FTM FTA FT% T) and a game log (PTS FTM FTA T). Playoff
  stats stay apart from the regular season's. Technical fouls count both.
* **Home page.** The two leader tiles (points per game, free throw %) and the top five of the points per game, free
  throw % and points lists (not technical fouls: that list is on the Stats page only).

Players are always "First L." (with the jersey number in front when `players.yml` has one). Never full names.
