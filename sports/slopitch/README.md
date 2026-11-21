# Slo-pitch

Seven innings, a run limit, a mercy rule, and an optional batting line for every player. The game file is a copy of
the scorebook page: you copy the runs of each inning, the R / H / E boxes and, if the league keeps them, each batter's
line. The site works out the score, the line score with its limit innings and Xs, each player's average and the
standings. If a box does not add up, the check names it and **nothing is published**.

This page is for whoever types the game files. How the files fit into a season is in `docs/data.md`; this page is the
`sheet:` part. The checks live in `rules.py`; `fixtures/` holds one game for every check below, and the JavaScript copy
of the rules (for the entry page, stage 7) is tested against the same files.

- [The game file](#the-game-file)
- [The boxes](#the-boxes)
- [How the numbers come from it](#how-the-numbers-come-from-it)
- [The X, the walk-off, the run limit and the mercy rule](#the-x-the-walk-off-the-run-limit-and-the-mercy-rule)
- [What is checked](#what-is-checked)
- [How to](#how-to): a called game, extra innings, a coin toss, a substitute, a spare, a game without batting lines,
  a forfeit
- [Settings the league may change](#settings-the-league-may-change)
- [What the site shows](#what-the-site-shows)

Words: a game has seven **innings**; each inning has a **top half** (the visitors bat) and a **bottom half** (the home
team bats). A team's runs in a half-inning are capped by the **run limit** (often 5); an inning with no cap is an
**open inning** (usually the last one). The **mercy rule** (run rule) ends a game early when one team leads by a set
number of runs after a set number of innings. A game stopped early (mercy rule, time limit, weather, darkness) is a
**called game**. A tie after seven innings may go to **extra innings**. A **walk-off** is when the home team takes the
lead in its last half-inning: the game ends there, and the bottom half of the last inning is not played if the home team
already leads (an **X**). The scorebook's **R / H / E** boxes are runs, hits and errors. A **batting line** is a player's
AB (at-bats), R (runs), H (hits), RBI (runs batted in), HR (home runs) and BB (walks); PA (plate appearances) is AB + BB
here, AVG (batting average) is H / AB, written `.333`, and OBP (on-base percentage) is (H + BB) / (AB + BB). A
**diamond** is one field and a **week** is one game day; both live in `schedule.csv` (`date`, `time`, `surface`), not in
the game file.

## The game file

The top part is the same for every sport (`game_id`, `status`, `home`, `away`, `scorekeeper`, `checked_by`: see
`docs/data.md`). The sport's part is `sheet:`. Sides are always `home` and `away`, never team ids. **`home` is the team
that bats last** (the scorebook's "Home" line), `away` the visitors; the site lists the visitors first ("Mudcats at
Sluggers"). Umpires' names are not copied: no page shows them.

```yaml
game_id: 2027-06-16-1
status: final
home: sluggers                 # bats last
away: mudcats
scorekeeper: Bev S.
checked_by: Ted F.
sheet:
  runs:                        # one box per inning played; the first box is the first inning
    away: [2, 0, 5, 1, 0, 3, 0]
    home: [1, 5, 0, 3, 5, 0, X]   # X: Sluggers led 14-11 after the top of the 7th, so they did not bat
  totals:                      # the R H E boxes as written (no e: this league does not keep errors)
    away: {r: 11, h: 15}
    home: {r: 14, h: 18}
  batting:                     # the batting order, top to bottom; a line each because this league keeps batting lines
    away:
      - {player: norm-w,    ab: 4, r: 2, h: 3, rbi: 0, hr: 0, bb: 0}
      - {player: sheila-r,  ab: 4, r: 1, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: phil-g,    ab: 4, r: 2, h: 2, rbi: 3, hr: 1, bb: 0}
      - {player: doug-e,    ab: 4, r: 1, h: 2, rbi: 2, hr: 0, bb: 0}
      - {player: pat-o,     ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: ken-j,     ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: marg-l,    ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
      - {player: brian-c,   ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: elaine-v,  ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: stan-z,    ab: 3, r: 0, h: 1, rbi: 0, hr: 0, bb: 0}
    home:
      - {player: gary-t,    ab: 4, r: 2, h: 3, rbi: 0, hr: 0, bb: 0}
      - {player: linda-m,   ab: 4, r: 2, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: ron-b,     ab: 4, r: 2, h: 3, rbi: 3, hr: 1, bb: 0}
      - {player: dave-k,    ab: 3, r: 2, h: 2, rbi: 4, hr: 1, bb: 0}
      - {player: bev-s,     ab: 3, r: 1, h: 2, rbi: 2, hr: 0, bb: 0}
      - {player: wayne-h,   ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: carol-d,   ab: 3, r: 1, h: 2, rbi: 1, hr: 0, bb: 0}
      - {player: ted-f,     ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
      - {player: joan-p,    ab: 3, r: 1, h: 1, rbi: 1, hr: 0, bb: 0}
      - {player: murray-l,  ab: 3, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}
```

That is `fixtures/clean.yml` (with Alpha and Bravo for the team names). In a draft (`drafts/`) any box may be left empty
(`~`), as for every sport.

## The boxes

Boxes count from 0 in a problem's path, like list positions: `runs.home.6` is the **seventh** inning's box of the home
team, `batting.away.4` the fifth batter of the visitors. A problem's path always starts with `sheet.` in the message
(`sheet.runs.home.6`); the paths below leave that off.

| Box | What goes in it |
|---|---|
| `runs.<side>` | One box per inning played, 1 to `rules.innings` + 10 boxes: a whole number from 0 to 99, or `X`. Both teams have the **same number of boxes**; the first box is the first inning. |
| `runs.<side>.<i>` | The runs that team scored in that half-inning, as written. A half-inning that ended at the run limit shows the limit (a circled 5 on the sheet). `X` is written, not worked out: the half was not played ([The X](#the-x-the-walk-off-the-run-limit-and-the-mercy-rule)). |
| `totals.<side>` | The R H E boxes: `{r, h, e}`. `r` is always written and must equal the sum of the innings. `h` only when the league keeps team hits (`rules.team_hits`, the default): left out when the batting lines are written (the lines' sum is used, and if both are written they must agree). `e` only when the league keeps errors (`rules.team_errors: kept`). |
| `called` | Only for a game shorter than regulation: `mercy`, `time`, `weather`, `darkness` or `other`: why the game stopped. |
| `bats_first` | Only `home`, after a coin toss sent the home team up first ([A coin toss](#a-coin-toss)). Leave it out when the visitors batted first. |
| `batting.<side>` | The batting order, top to bottom: 1 to 30 rows `{player, ab, r, h, rbi, hr, bb}`. `player` is the id from `players.yml`. The row's position is the batting order; a row is a game played. The line (`ab r h rbi hr bb`) only when the league keeps batting lines (`rules.batting`). |
| `batting.<side>.<i>` | A row may carry `name` instead of `player` (drafts only: a spare written in by hand, not yet in `players.yml`; such a row counts for nobody). |

The six numbers of a line are whole numbers from 0 to 20. Write `0` for none: an empty box is a gap.

## How the numbers come from it

| Number | From |
|---|---|
| The score | The sum of each team's runs. The R box must agree. The score of a game decided in extra innings is the same sum. |
| The line score | The runs by inning, one column for each regulation inning (the ones a called game never reached are marked "not played") and one for each extra inning. |
| Decided in | `overtime` when extra innings were played (the pages say "Extras"), else regulation. A regular-season game level at the end is a tie. |
| Limit innings | A box that equals the run limit, in an inning that has the limit, is circled on the game page and listed under "Limit innings". The sheet does not say whether the third out came first, so the mark means "reached the limit". |
| Games played | A batting-order row with a `player` is one game, whether or not the row has a line. |
| A player's line | The six numbers of the row. PA = AB + BB; AVG = H / AB; OBP = (H + BB) / (AB + BB); none of the three is shown for a player with nothing at the plate. |
| Team H | The H box; or, when there is none, the sum of the H column. |
| Walk-off | The team batting last, in the last regulation inning or an extra inning, was behind or level after the top half and ended the game ahead. |
| Top bat (the result card) | The player with the most hits (at least one), then the fewest at-bats, then the most RBI, then the first in the order of play. Not shown for a game with no batting lines. |

Players with a batting line in some games and not in others are shown with the numbers of the games that have lines;
their GP counts every game, so do not divide by it.

## The X, the walk-off, the run limit and the mercy rule

**X.** The team batting last does not bat the bottom of the last inning when it already leads after the top half: the
game is over. The sheet has an `X` there, and so does the game file. `X` means something different from `0`: a `0` is a
half-inning in which the team batted and scored nothing. The checks make sure an `X` is only where the rules allow it:
in the team batting last, in the last inning of the list, and only when that team led after the top half. If it was
level or behind, it had to bat: write its runs. Conversely, a number in that box when the team led is only a warning
("not needed: write X"): some leagues play the last half out for fun, and the runs stay. A called game can also end on
an `X` (the top half was played, the home team led, and time ran out).

**Walk-off.** In the last regulation inning or an extra inning the team batting last may take the lead; the game ends
when the winning run scores, so only a home run can bring in more runs than it needed. A walk-off half with more than
the needed runs plus three (a grand slam on the winning play) is a warning ("check the box"); the runs stay.

**Run limit.** `rules.run_limit` (default 5) is the most runs a team may score in one half-inning. By default the last
inning and every extra inning are open (`rules.open_innings: last`); `none` limits every inning. With
`rules.limit_play: stop` (the default) a box is at most the limit; with `finish` every run on the play that reached the
limit counts, so a box may be up to the limit plus 3. More than that is an error. `run_limit: 0` is no limit.

**Mercy rule.** `rules.mercy_runs` (default 15) after `rules.mercy_after` innings (default 5; 4½ when the team batting
last leads, which is the top half of the 5th and an `X`). It is only looked at when the sheet says `called: mercy`, and
only as a warning: leagues word it differently, and the sheet records what happened. A game played out to the end in
spite of a big lead is not flagged. `mercy_runs: 0` is no mercy rule, and `called: mercy` is then an error.

## What is checked

Every problem has a path (the box), a level, and one sentence that says what to do. An **error** stops the build. A
**warning** is shown and never stops it. A **gap** is an empty box: an error in `games/`, a warning in `drafts/`, so a
draft is never stricter than a finished file. Unknown lines are errors at every level, because they are nearly always
typos. Paths below are relative to `sheet`; `<side>` is `home` or `away`, `<i>` counts from 0, "the final inning" is the
last box of the list, and "the team batting last" is `home` unless `bats_first: home`. When a problem makes later checks
meaningless (a bad `runs` list), the later checks of that part are skipped.

| Path | What is wrong | Level |
|---|---|---|
| `<key>` | a line other than `runs totals called bats_first batting` | error |
| `""` (the whole sheet) | not a block | error |
| `bats_first` | not `home` or `away` | error |
| `runs` | missing | gap |
| `runs` | not a block | error |
| `runs.zzz` | a side that is not `home` or `away` | error |
| `runs.<side>` | missing | gap |
| `runs.<side>` | not a list of 1 to `rules.innings` + 10 boxes | error |
| `runs.<side>` | the two lists have different lengths (the shorter one is named): "write X for a bottom half not needed" | error |
| `runs.<side>.<i>` | empty | gap |
| `runs.<side>.<i>` | not a whole number from 0 to 99 or `X` | error |
| `runs.<side>.<i>` | `X` in the team batting first, or in any box but the final inning's | error |
| `runs.<side>.<i>` | `X` although the team batting last did not lead after the top half ("Sluggers trailed 9-11 after the top of the 7th, so they batted: write their runs") | error |
| `runs.<side>.<i>` | a number in the final box of the team batting last although it led after the top half, in an inning that ends the game (the last regulation inning or an extra inning): "not needed, write X" | warning |
| `runs.<side>.<i>` | more runs than `rules.run_limit` in a limited inning; with `limit_play: finish`, more than the limit plus 3 | error |
| `runs.<side>.<i>` | a walk-off half with more than the runs needed plus 3 | warning |
| `runs.<side>.<innings>` | more innings than `rules.innings` although the score was not level after regulation | error |
| `runs.<side>.<i>` | in a regular-season game, an inning past `rules.extra_innings` (the first one not allowed: no extra inning, or the ones the league plays) | error |
| `runs.<side>.<i>` | an extra inning played after a team led at the end of a complete extra inning (the game was over) | error |
| `called` | missing in a game of fewer than `rules.innings` innings ("a 5-inning game: if it was called, add `called:`...") | error |
| `called` | not `mercy`, `time`, `weather`, `darkness` or `other` | error |
| `called` | set on a game of `rules.innings` innings or more | error |
| `called` | `mercy` when `rules.mercy_runs` is 0 (no mercy rule) | error |
| `called` | `mercy`, and the lead at the end is less than `rules.mercy_runs`, or fewer than `rules.mercy_after` innings were played | warning |
| `called` | a called game shorter than `rules.official_innings` ("does it count? A game that is replayed stays out of `games/`") | warning |
| `totals` | missing | gap |
| `totals` | not a block | error |
| `totals.zzz` | a side that is not `home` or `away` | error |
| `totals.<side>` | missing | gap |
| `totals.<side>` | not a row; a key other than `r h e` (`.<key>`) | error |
| `totals.<side>.r` | missing | gap |
| `totals.<side>.r` | not a whole number | error |
| `totals.<side>.r` | not the sum of the side's runs ("R says 12, the innings add up to 11") | error |
| `totals.<side>.h` | missing, when `rules.team_hits` is `kept` and the side has no batting lines | gap |
| `totals.<side>.h` | set, when `rules.team_hits` is `none` and the side has no batting lines | error |
| `totals.<side>.h` | not a whole number from 0 to 99 | error |
| `totals.<side>.h` | not the sum of the side's batting lines' H | error |
| `totals.<side>.e` | missing, when `rules.team_errors` is `kept` | gap |
| `totals.<side>.e` | set, when `rules.team_errors` is `none`; not a whole number from 0 to 99 | error |
| `batting` | missing, when `rules.batting` is not `none` | gap |
| `batting` | set, when `rules.batting` is `none` ("this league keeps team results only") | error |
| `batting` | not a block | error |
| `batting.zzz` | a side that is not `home` or `away` | error |
| `batting.<side>` | missing | gap |
| `batting.<side>` | not a list of 1 to 30 rows | error |
| `batting.<side>.<i>` | not a row; an unknown key (`.<key>`, one of `player name ab r h rbi hr bb`) | error |
| `batting.<side>.<i>.player` | missing (a row with only a `name`: a spare not yet in `players.yml`) | gap |
| `batting.<side>.<i>.player` | not in `players.yml`; listed twice in the game | error |
| `batting.<side>.<i>.player` | on another team and not `sub: true` | warning |
| `batting.<side>.<i>.<key>` | a line key (`ab r h rbi hr bb`), when `rules.batting` is `order` (the first one is named) | error |
| `batting.<side>.<i>` | a row with no line, when `rules.batting` is `every_game` | gap |
| `batting.<side>.<i>` | with `optional`: some rows of a side have a line and some do not ("all of a team's batters have a line, or none"; the first row without one is named) | error |
| `batting.<side>` | with `optional`: one side has lines and the other does not ("only Bravo has batting lines: is a page missing?"; the side without is named) | warning |
| `batting.<side>.<i>.<key>` | a line key empty | gap |
| `batting.<side>.<i>.<key>` | a line value not a whole number from 0 to 20 | error |
| `batting.<side>.<i>.h` | more than `ab` | error |
| `batting.<side>.<i>.hr` | more than `h` | error |
| `batting.<side>.<i>.ab` | plate appearances (`ab` + `bb`) more than the innings the side batted plus 2 ("check the line") | warning |
| `batting.<side>` | the R column does not add up to the side's runs ("the batters' R add up to 10, the team scored 11") | error |
| `batting.<side>` | the RBI column adds up to more than the side's runs | warning |
| `batting.<side>` | the side's home runs are more than `rules.hr_limit` (when set) | warning |

The core then adds, at `sheet.totals.<side>.r`, an error for a tied playoff game, and for a tied regular-season game
when `standings.ties` is `false`.

## How to

### A called game

A game that stopped early (the mercy rule, the time limit, weather, darkness) keeps the score as it stood. Write only
the innings that were played, the same number of boxes for both teams, and add `called` with the reason:

```yaml
sheet:
  runs:                       # 22-4 after five innings: the mercy rule
    away: [3, 5, 5, 4, 5]
    home: [0, 1, 0, 2, 1]
  called: mercy               # mercy, time, weather, darkness or other
  totals:
    away: {r: 22, h: 24}
    home: {r: 4, h: 6}
  batting: ...                # the batting order as usual
```

If the team batting last led after the top half and did not bat, end its list with `X` as usual (`home: [..., X]`): the
game counts that as 4½ innings for the mercy rule. A game under 4 innings (`rules.official_innings`) is a warning:
"does it count?" If the league's rule is that an unfinished inning does not count ("the score reverts to the last full
inning"), leave that inning out of both lists yourself. A game that is replayed stays out of `games/` altogether. The
time limit (`rules.time_limit`) is only shown on the game page ("After 6 innings: time limit, 60 minutes"); the sheet
records no clock, so nothing checks it.

### Extra innings

A regular-season game level after seven innings is a tie (`rules.extra_innings: 0`, the default): leave it at seven.
A league that plays one extra inning sets `rules.extra_innings: 1`. A **playoff** game plays extra innings until the
game is decided; write the extra innings as more boxes, both teams the same number, and the last one an `X` if the team
batting last led after the top half. Extra innings are open (no run limit) with `open_innings: last`:

```yaml
sheet:                        # a playoff game: 9-9 after seven, a scoreless 8th, a walk-off in the 9th
  runs:
    away: [1, 0, 2, 0, 3, 1, 2, 0, 2]
    home: [0, 3, 1, 2, 0, 2, 1, 0, 3]
```

The score is the sum of every box, and the game is "Final · Extras". Do not write an extra inning when the score was
not level after a complete inning: that is an error.

### A coin toss

When a coin toss sends the home team up first, `home` is still the team that is "Home" on the sheet, but it bats first.
Add `bats_first: home`; the `X` rule then applies to the visitors, who bat last:

```yaml
sheet:
  bats_first: home
  runs:
    home: [1, 0, 2, 0, 3, 1, 0]
    away: [2, 3, 1, 2, 1, 0, X]    # the visitors batted last and led after the top of the 7th
```

The game page lists the team that batted first on the top row of the line score, and its batters first. Leave
`bats_first` out for every game the visitors batted first.

### A substitute

A substitute is a row of their own right under the player they replaced, with their own line for the innings they
batted. A run counts for the row the scorebook writes it on (no courtesy runner key: write the runs on the row the
scorekeeper credited). The game counts as a game played for both players.

```yaml
    home:
      - {player: gary-t, ab: 2, r: 1, h: 1, rbi: 0, hr: 0, bb: 0}      # left after two at-bats
      - {player: ted-f,  ab: 2, r: 1, h: 2, rbi: 1, hr: 0, bb: 0}      # came in for Gary T.
      - {player: linda-m, ...}
```

### A spare

A spare (a player who fills in for either team) is in `players.yml` with `sub: true` and no team, and is a row in the
batting order like any other. A player of another team who is not marked `sub: true` is a warning ("Hal C. is not on
Bravo"), so mark the spare. A spare who is not in `players.yml` yet can be written in a draft by name,
`{name: Jo K., ab: 3, ...}`: that row counts for nobody and is an error in `games/` until the spare is added to
`players.yml` and the row names the `player`.

### A game without batting lines

With `rules.batting: optional` (the default) a game may have a line for every batter, or none: write only the order,
and the H box.

```yaml
sheet:
  runs: {away: [2, 0, 3, 1, 0, 3, 1], home: [1, 3, 0, 2, 4, 0, 0]}
  totals:
    away: {r: 10, h: 12}
    home: {r: 10, h: 11}
  batting:
    away: [{player: norm-w}, {player: sheila-r}, {player: phil-g}, ...]
    home: [{player: gary-t}, {player: linda-m}, ...]
```

Every player in the order still gets a game played; the season's batting totals come from the games that have lines. All
of a team's batters have a line, or none (a mixed team is an error); one team with lines and one without is a warning.
A league that never keeps lines sets `rules.batting: none` (no `batting` at all; the Stats page then has no player
table); a league that keeps only the order sets `order`; `every_game` makes a missing line a gap.

### A forfeit

A forfeit has no sheet. The game file names the team that forfeited and leaves `sheet:` out:

```yaml
game_id: 2027-06-23-2
status: final
home: sluggers
away: mudcats
checked_by: Ted F.
forfeit: mudcats
```

No player gets a game played. How the score counts (default: 7 to 0, shown as `[placeholder]`) is the league's to decide
under `standings: forfeit:` in `league.yml`.

## Settings the league may change

Set in `league.yml` under `rules:`, `standings:` and `stats.minimums:`; each one marked *decide* shows as
`[placeholder]` on the site, and in the build's "Still to decide" list, until the league sets it (even to the usual
value).

| Setting | Values | Default |
|---|---|---|
| `rules.innings` | 3 to 9: innings in a game | 7 (*decide*) |
| `rules.run_limit` | 0 to 20: most runs in one half-inning (0 is no limit) | 5 (*decide*) |
| `rules.open_innings` | `last`, `none`: the last inning and every extra inning have no limit, or every inning has it | `last` (*decide*) |
| `rules.limit_play` | `stop`, `finish`: runs on the play that reaches the limit stop at the limit, or all count | `stop` (*decide*) |
| `rules.mercy_runs` | 0 to 30: the lead that ends a game early (0 is no mercy rule) | 15 (*decide*) |
| `rules.mercy_after` | 1 to 9: innings before the mercy rule applies | 5 (*decide*) |
| `rules.official_innings` | 1 to 9: innings that make a called game count | 4 (*decide*) |
| `rules.time_limit` | 0 to 180 minutes (0 is none): only shown on the game page | 60 (*decide*) |
| `rules.extra_innings` | 0 to 5: extra innings in a regular-season game (playoffs play until decided) | 0 (*decide*) |
| `rules.hr_limit` | 0 to 10: home runs one team may hit in a game (0 is none); passing it is a warning | 0 (*decide*) |
| `rules.batting` | `none`, `order`, `optional`, `every_game`: what the sheet keeps for each batter | `optional` |
| `rules.team_hits` | `kept`, `none`: the H box | `kept` |
| `rules.team_errors` | `none`, `kept`: the E box (and a column) | `none` |
| `stats.minimums.avg_min_pa` | plate appearances per team game a player needs to rank on AVG and OBP | 2 (*decide*) |
| `standings.points` | `{win, tie, loss}` | 2, 1, 0 (an extra-inning win and loss count as a win and a loss) |
| `standings.ties` | `true`, `false` | `true` (*decide*) |
| `standings.forfeit` | `{score: [7, 0]}` | `[7, 0]` (*decide*) |
| `standings.tiebreakers` | `head_to_head`, `diff`, `wins`, `points_for`, ... `{diff: {cap: 7}}` caps each game's margin | head-to-head, then run difference capped at 7 a game (*decide*) |
| `standings.columns` | `gp w l t pts pf pa diff pct ...` | `gp w l t pts pf pa` |

The average minimum is "per team game": a player needs the setting times the games their team has played, so the board
fills from week 1 and stays fair. (A fixed "15 at-bats" would leave it empty for weeks.)

Common variants:

```yaml
rules: {innings: 5, mercy_runs: 10, mercy_after: 3}               # a short-game league
rules: {run_limit: 0}                                             # no run limit
rules: {extra_innings: 1}                                         # one extra inning in the regular season
rules: {limit_play: finish}                                       # the play that reaches the limit counts in full
rules: {batting: none}                                            # team results only
rules: {team_errors: kept}                                        # an E box and an E column
standings: {rank_by: win_pct, columns: [gp, w, l, t, pct, pf, pa]}   # many rain-outs and unequal schedules
standings: {tiebreakers: [head_to_head, diff]}                    # run difference with no cap
standings: {columns: [gp, w, l, t, pts, pf, pa, diff]}            # a DIFF column
```

A league's co-ed rules (a batting order that alternates, a walk after a home run) are not a setting and not checked: the
site keeps no personal data beyond "First L.". They go on the league's rules page.

## What the site shows

* **Game page:** the final panel with the visitors first ("Mudcats at Sluggers") and "Final · Extras" for an extra-inning
  game; the line score with a column for each inning, the open innings marked, circled limit boxes, `X` for a half not
  needed (or an inning a called game never reached), R, then H (and E when kept), and a short key; "Home runs",
  "3+ hits", "Limit innings" and "Called" facts; each team's batting table (#, Batter, AB R H RBI HR BB and a Totals
  row) or, when the league keeps the order only, a "Batting order" list.
* **Result cards** (Home, Schedule, team pages) show the line score ("Final · Diamond 1") and the top bat.
* **Standings:** GP W L T PTS RF RA.
* **Stats:** one Batting table and leaders for batting average, home runs, RBI, hits, runs and on-base percentage, only
  while the league keeps batting lines (`optional` or `every_game`). A player needs `avg_min_pa` plate appearances per
  team game to rank on AVG and OBP. With `batting: order` the Stats page lists every player with games played only;
  with `none` there is no player table, no leaders and no player page stats.
* **Players** are shown as "First L." with their jersey number from `players.yml`, when they have one; no full names,
  contact details or photos.
