# Curling

Ends, a hammer (the last stone of an end) and a club score card with one box per end for each rink. The game file
is a box-for-box copy of that card: you copy what is written, and the site works out the final score, who stole
which end, the "game in numbers" and the standings. If a box does not add up, the check names it and **nothing is
published**.

This page is for whoever types the game files. How the files fit into a season is in `docs/data.md`; this page is
the `sheet:` part. The checks live in `rules.py`; `fixtures/` holds one game for every check below, and the
JavaScript copy of the rules (for the entry page, stage 7) is tested against the same files.

- [The game file](#the-game-file)
- [The boxes](#the-boxes)
- [The hammer](#the-hammer)
- [How the numbers come from it](#how-the-numbers-come-from-it)
- [What is checked](#what-is-checked)
- [How to](#how-to): a concession, time called, an extra end, a spare, a three-player rink, a forfeit
- [Naming rinks](#naming-rinks)
- [Settings the league may change](#settings-the-league-may-change)
- [What the site shows](#what-the-site-shows)

Words: an **end** is one round of 16 stones; only one rink scores in an end, or nobody does (a **blank end**).
The **hammer** is the last stone of an end. A rink that scores without it has **stolen** the end. A **rink** is a
team of four: lead, second, vice and skip (the skip leads it and throws last). Rinks **shake hands** to concede.
A **draw** is one game time and a **sheet** is one lane of ice (A, B, C...); both live in `schedule.csv`
(`date`, `time`, `surface`), not in the game file.

## The game file

The top part is the same for every sport (`game_id`, `status`, `home`, `away`, `scorekeeper`, `checked_by`: see
`docs/data.md`). The sport's part is `sheet:`. Sides are always `home` and `away`, never team ids; "home" only means
the first-listed rink (pages say "vs").

```yaml
game_id: 2026-12-01-1
status: final
home: button-pushers
away: hurry-hard
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  hammer: away                 # which rink threw the last stone of end 1 (the LSFE box on the card)
  ends:                        # points per end, end 1 first; 0 for the rink that did not score; X = not played
    home: [0, 0, 1, 1, 0, 3, 0, 2]
    away: [0, 2, 0, 0, 1, 0, 2, 0]
  final: {home: 7, away: 5}    # the Total boxes, as written
  lineups:                     # in throwing order, lead first, as on the card
    home:
      - {player: carol-d, position: lead}
      - {player: ken-w, position: second}
      - {player: linda-f, position: vice}
      - {player: doug-h, position: skip}
    away:
      - {player: pat-o, position: lead}
      - {player: ron-m, position: second, spare_for: brian-s}    # a spare, here for Brian S.
      - {player: joanne-t, position: vice}
      - {player: wayne-b, position: skip}
```

Here Hurry Hard had the hammer in end 1 and nobody scored (a blank end, so they kept it), Button Pushers stole end 4
and Ron M. spared for Brian S. A forfeit has no `sheet` at all: see [A forfeit](#a-forfeit).

In a **draft** (`drafts/`, never built) any box may be left empty (`~`), and a lineup row may be `{name: Jo K., position: second}`
for a spare who is not in `players.yml` yet.

## The boxes

Ends and lineup rows count from 0 in a problem's path, like list positions: `ends.home.3` is **end 4**, `lineups.away.1`
is the second row. A problem's path always starts with `sheet.` in the message (`sheet.ends.away.3`); the paths below
leave that off.

```
          end   1   2   3   4   5   6   7   8     EE (extra ends)   Total
 ends.home.0 ..                     ends.home.7      extra.home.0     final.home
 ends.away.0 ..                     ends.away.7      extra.away.0     final.away
 hammer: who threw last in end 1          lineups.home.0 .. lineups.home.3 (throwing order)
```

| Box | What goes in it |
|---|---|
| `hammer` | `home` or `away`: the rink that threw the last stone of the first end. Required. Every later end's hammer is worked out ([The hammer](#the-hammer)). |
| `ends.<side>` | One entry per end, exactly as many as the league plays (`rules.ends`, 8 unless set). A number from 0 to 8, or `X` for an end not played. |
| `extra.<side>` | One entry per extra end, only when the game was level after the last end ([An extra end](#an-extra-end)). |
| `conceded` | The rink that shook hands (`home` or `away`): [A concession](#a-concession). The ends left are `X`. |
| `time_called` | `true` when ice time ran out: [Time called](#time-called). The ends left are `X`. |
| `final.<side>` | The Total boxes, as written. They must equal the ends plus the extra ends. |
| `lineups.<side>` | Three or four rows in throwing order, each `{player, position}` (and `spare_for` for a spare). Only when `rules.lineups` is `recorded`. |
| `.player` | The player's id from `players.yml`. A spare not yet in `players.yml` has `name: Jo K.` instead (a **draft** only). |
| `.position` | `lead`, `second`, `vice` or `skip`. Each is played once in a rink; every rink has a skip. |
| `.spare_for` | For a spare: the regular player of this rink who was not there. |

## The hammer

The rule the site uses (standard four-player curling):

1. The rink named in `hammer` has the hammer in end 1.
2. If the rink **with** the hammer scores, it gives the hammer up: the other rink has it next end.
3. If the rink **without** the hammer scores, it has **stolen** the end. The rink that had the hammer keeps it.
4. If nobody scores (a **blank end**), the rink that had the hammer keeps it.

Extra ends follow the same rule. This is why only the first hammer is written in the file: the rest follows from
the scores, so a second record of it could only disagree. A card that marks the hammer in every end is copied by its
first mark. (Mixed doubles passes the hammer on after a blank end; this sport is for four-player rinks and does not.)

## How the numbers come from it

| Number | From |
|---|---|
| Final score | The ends plus the extra ends (the Total boxes must agree). |
| Ends won (EW) | The ends a rink scored in, extra ends included. |
| Stolen ends (SE) | The ends a rink scored in without the hammer. |
| Ends with hammer (HE) | The ends played with the hammer, blank ends included. |
| Scored with hammer (HS) | The ends a rink scored in with the hammer: "3 of 5" is HS of HE. Any score counts; this is not the "hammer efficiency" some analysts quote (two or more). |
| Blank ends (BE) | The blank ends, counted to the rink that had the hammer and kept it. |
| Big ends (3+) | The ends a rink scored 3 or more in. |
| Ends played (E) | The ends played, extra ends included (only for "of 54 ends" style details). |
| Games played | One for every lineup row that has a player id. A spare gets the game, not the regular they replaced. A rink with no lineup recorded (`rules.lineups: none`) has no games played. |
| Extra end | Played when the `extra` boxes are filled in. The winner of an extra end has an overtime win, which counts as a full win unless the league says otherwise. |

Players have **no counting stats** beyond games played, and no player leaderboards. A player's position is the one in
`players.yml` (the player page shows "Skip · 2026-27 season").

## What is checked

Every problem has a path (the box), a level, and one sentence that says what to do. An **error** stops the build. A
**warning** is shown and never stops it. A **gap** is an empty box: an error in `games/`, a warning in `drafts/`, so a
draft is never stricter than a finished file. Unknown lines are errors at every level, because they are nearly always
typos.

| Path | What is wrong | Level |
|---|---|---|
| `<key>` | a line other than `hammer ends extra conceded time_called final lineups` | error |
| `""` (the whole sheet) | not a block | error |
| `hammer` | missing | gap |
| `hammer` | not `home` or `away` | error |
| `ends` | missing, or not a block with `home` and `away` | gap |
| `ends.<side>` | missing from the block | gap |
| `ends.zzz` | a side that is not `home` or `away` | error |
| `ends.<side>` | not a list of exactly `rules.ends` boxes ("this league plays 8 ends: write 8 boxes, X for an end not played") | error |
| `ends.<side>.<i>` | empty | gap |
| `ends.<side>.<i>` | not a whole number from 0 to 8, or `X` (a lower-case `x` is not `X`) | error |
| `ends.<side>.<i>` | 7 or 8 ("very rare: check the card") | warning |
| `ends.home.<i>` | both rinks scored in one end (only one rink scores in an end) | error |
| `ends.<side>.<i>` | `X` for one rink and a number for the other (reported at the `X`) | error |
| `ends.<side>.<i>` | a number after an `X` (`X` marks only the ends left when a game stopped early) | error |
| `ends.home.0` | `X`: no end was played, which is a forfeit, not a score | error |
| `ends.<side>.<i>` | the first `X`, with neither `conceded` nor `time_called` set | error |
| `conceded` | not `home` or `away`; set although every end was played; set together with `time_called` | error |
| `conceded` | the rink that shook hands was not behind (level counts as not behind) | error |
| `time_called` | not `true` | error |
| `extra` | not a block with `home` and `away` lists | error |
| `extra.zzz` | a side that is not `home` or `away` | error |
| `extra.<side>` | not a list | error |
| `extra.away` | the two lists are not the same length | error |
| `extra.<side>.<i>` | empty | gap |
| `extra.<side>.<i>` | not a whole number from 0 to 8 (`X` is for ends not played, and an extra end is always played) | error |
| `extra` | filled in, but the game was not level after the last end, or it stopped early | error |
| `extra` | filled in for a regular-season game when `rules.extra_end` is `playoffs` | error |
| `extra.home.<i>` | both rinks scored; an extra end after the one that broke the tie; the last extra end blank (a game ends on a score, unless `time_called`) | error |
| `extra` | missing although the game was level after the last end, in a playoff game or with `rules.extra_end: always` (and not `time_called`, and not stopped early) | error |
| `final` | missing | gap |
| `final` | not a block | error |
| `final.zzz` | a side that is not `home` or `away` | error |
| `final.<side>` | missing | gap |
| `final.<side>` | not a whole number; not the ends plus the extra ends ("the Total box says 7, but the ends add up to 6") | error |
| `lineups` | filled in when `rules.lineups` is `none` | error |
| `lineups` | missing when `rules.lineups` is `recorded` | gap |
| `lineups` | not a block | error |
| `lineups.zzz` | a side that is not `home` or `away` | error |
| `lineups.<side>` | missing from the block | gap |
| `lineups.<side>` | not a list of 3 or 4 rows (a rink may play three; more than four never throw) | error |
| `lineups.<side>` | no skip (checked once every row has a good position) | error |
| `lineups.<side>.<i>` | not a row; an unknown key (`.<key>`) | error |
| `lineups.<side>.<i>.position` | missing; not `lead second vice skip`; the same position twice in a rink | error |
| `lineups.<side>.<i>.player` | missing (a row with only a `name`: a spare not yet in `players.yml`) | gap |
| `lineups.<side>.<i>.player` | not in `players.yml`; listed twice in the game | error |
| `lineups.<side>.<i>.player` | on another team, not `sub: true`, and no `spare_for` | warning |
| `lineups.<side>.<i>.spare_for` | not a regular player of this rink in `players.yml`; also in this lineup | error |
| `lineups.<side>.<i>.spare_for` | set on a row whose player is a regular of this rink | warning |

After these the core adds one more, at `final.home`: a **tied playoff game** (only reachable when `time_called` stops a
level game, since a level playoff game needs an extra end), and a **tied regular-season game when `standings.ties` is
false**. It names the Total box of the first-listed rink.

When a box makes the later checks meaningless, checking stops there instead of listing a cascade: no end boxes (or
the wrong number of them) means no extra-end checks and no check of the Total boxes against the ends.

The checks that look at the whole file (`game_id` against the file name and the schedule, `status` against the folder,
`home` and `away` against the schedule, `checked_by`, `forfeit`) are the core's: see `docs/data.md`.

## How to

### A concession

When a rink shakes hands, the game ends after the last **complete** end. The score stands as it is, so the rink that
conceded must be behind. Write `X` in the boxes of the ends that were not played, for both rinks, and name the rink:

```yaml
  ends:                        # Free Guards shook hands after end 6
    home: [0, 2, 2, 0, 3, 1, X, X]
    away: [1, 0, 0, 2, 0, 0, X, X]
  conceded: away
  final: {home: 8, away: 3}
```

A concession is a normal win and loss, not a forfeit: the ends played count in every stat, and the game page says
"Shook hands after 6 of 8 ends". There is no minimum number of ends before a rink may concede. Conceding while level
or ahead is an error (check which rink conceded), and so is `conceded` when every end was played.

### Time called

If ice time runs out, the game stops after the last complete end. Write `X` in the ends not played and
`time_called: true` (instead of `conceded`):

```yaml
  ends:
    home: [1, 0, 2, 0, 0, 1, 0, X]
    away: [0, 1, 0, 1, 0, 0, 0, X]
  time_called: true
```

The game is counted as it stands. Level at that point it is a **tie**: fine in a regular-season game where the league
allows ties; in a playoff game, or where ties are not allowed, the core reports it at `final.home` and the league has
to decide how to settle it. A blank last extra end is allowed when time was called.

### An extra end

If the game is level after the last scheduled end (`ends`), what happens depends on the league (`rules.extra_end`):

* `playoffs` (the default, shown as `[placeholder]`): a regular-season game that is level is a **tie** (nothing to
  write), and a playoff game goes on to an extra end.
* `always`: every level game goes on to an extra end.

Write one box per rink for each extra end played, first extra end first:

```yaml
  ends: {home: [1, 0, 2, 0, 0, 1, 0, 0], away: [0, 1, 0, 1, 2, 0, 0, 0]}   # a playoff game, 4-4 after eight
  extra: {home: [0, 1], away: [0, 0]}    # the first extra end was blank (keep playing); home scored 1 in the second
  final: {home: 5, away: 4}
```

* Extra ends go on until one ends with a score. A blank extra end means another one, and the hammer stays where it
  was, as in any blank end.
* The Total boxes include the extra ends.
* An extra-end win counts as a full win in the standings (2 points) unless the league changes `points.ot_win`.
* The game page shows an `EE` column per extra end ("EE1", "EE2"... when there are several) and "Final · EE".
* An `extra` on a game that was not level, on a game that stopped early, or (with `extra_end: playoffs`) on a
  regular-season game is an error; so is a level playoff game with no `extra`.

### A spare

A spare is anyone who is not on the rink's roster that night.

1. Add them to `players.yml` first: `{id: ron-m, name: Ron M., team: null, sub: true}` (a spare who belongs to no
   rink).
2. In the lineup, give their row the id and say who they replaced: `{player: ron-m, position: second, spare_for: brian-s}`.

The spare gets the game played; the regular they replaced does not. A regular player of another rink who fills in is
already in `players.yml`: add `spare_for`, or mark them `sub: true` there, or the check warns you
(`... is not on <rink>`). A warning never stops the build. `spare_for` must name a regular of this rink who is not also
in the lineup.

If you are typing the file before you know who the spare is, write the row as it is on paper,
`{name: Jo K., position: second}`, and save it as a **draft** (`drafts/`). A finished file cannot have such a row:
it is an error, because the game would have nobody to count for.

### A three-player rink

A rink may play three. Write three rows in throwing order; every rink needs a skip, and each position is used once
(so leave out the position nobody played, usually the second):

```yaml
    home:
      - {player: carol-d, position: lead}
      - {player: linda-f, position: vice}
      - {player: doug-h, position: skip}
```

More than four rows is an error: only four throw.

### A forfeit

A forfeit has no sheet. The game file names the rink that forfeited and leaves `sheet:` out:

```yaml
game_id: 2026-12-08-2
status: final
home: free-guards
away: takeouts
checked_by: Lee M.
forfeit: takeouts
```

No player gets a game played and no team stat moves. How the score counts (default: 1 to 0, shown as `[placeholder]`)
is the league's to decide under `standings: forfeit:` in `league.yml`.

## Naming rinks

Clubs often call a rink after its skip ("Team Smith"). **Don't:** the site shows players as "First L." only, and a
rink named after the skip's surname puts that surname on every page. Name rinks with a made-up name ("Button
Pushers"), or by first name and initial ("Gail R.'s rink"). The build does not try to detect surnames. A team's skip is
shown on its card from `players.yml` (the player with `position: skip`), so the name does not need to say it.

## Settings the league may change

Set in `league.yml`; each one marked *decide* shows as `[placeholder]` on the site, and in the build's "Still to
decide" list, until the league sets it (even to the usual value).

| Setting | Values | Default |
|---|---|---|
| `rules.ends` | 4 to 10: the ends in a game (a game file has exactly that many boxes; per season with `overrides`) | 8 (*decide*) |
| `rules.extra_end` | `playoffs`, `always`: when a game level after the last end goes on to an extra end | `playoffs` (*decide*) |
| `rules.lineups` | `recorded`, `none`: whether game files list the players | `recorded` |
| `standings.points` | `{win, tie, loss, ot_win, ot_loss}` | 2, 1, 0 (an extra-end win and loss count as a win and a loss) |
| `standings.ties` | `true`, `false` | `true` (*decide*). A league that never allows ties sets `ties: false` **and** `extra_end: always` |
| `standings.forfeit` | `{score: [1, 0]}`, `{score: [8, 0]}`, `{score: per_period}` (1-0 in every end) | `[1, 0]` (*decide*) |
| `standings.tiebreakers` | `head_to_head`, `diff`, `points_for`, `periods_won`, ... | head-to-head, then point difference (*decide*) |
| `standings.period_points` | points for each end won | 0 |
| `standings.columns` | `gp w l t pts pf pa diff pw ...` and any team stat: `ends_won stolen blanks big_ends hammer_ends hammer_scored ends` | `gp w l t pts pf pa` |

Common variants:

```yaml
rules: {ends: 6}                                         # a six-end league
rules: {extra_end: always}                               # every level game goes to an extra end
standings: {ties: false}                                 # (together with extra_end: always)
standings: {tiebreakers: [head_to_head, periods_won]}    # rank on ends won
standings: {forfeit: {score: [8, 0]}}                    # a forfeit is 8-0
standings: {columns: [gp, w, l, t, pts, pf, pa, stolen]} # add stolen ends to the table
```

A last-stone draw total, common in competitive curling, is not on a score card and is not supported.

**Two "ends won" numbers.** `pw` (the "Ends won" tiebreaker and the `period_points` count) is the core's and counts the
scheduled ends only. The team stat `ends_won` counts extra ends too. They differ only after an extra end.

## What the site shows

* **Game page.** The final panel ("Final", "Final · EE" after an extra end); the end-by-end line score with the hammer
  marked in each end, stolen ends tinted, blank ends shaded and `X` for ends not played (title "End by end", with
  "8 ends · no extra end", "Shook hands after 6 of 8 ends" or "Time called after 7 of 8 ends"); "The game in numbers" (ends
  won, stolen ends, ends with hammer, scored with hammer, blank ends, big ends); and the lineups with a "Spare" badge
  ("for Brian S."). Without lineups (`rules.lineups: none`) there is no lineups block.
* **Result card.** A compact end table, "Sheet A · 6:30 PM", and "Shook hands after 6" when a rink conceded.
* **Standings.** GP W L T PTS PF PA, headed "Rink".
* **Stats page.** The rink leaders (stolen ends, ends won, big ends) and every player's games played.
* **Team page.** The skip is named on the card ("Skip Gail R."); the roster table shows games played.
* **Player page.** Position and games played; the game log has no stat columns.

Players are always "First L.". Never full names.
