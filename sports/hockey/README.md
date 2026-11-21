# Hockey

Periods, goals with up to two assists, penalties, goalies, and an optional overtime and shootout. The game file is a
copy of the scorekeeper's game sheet: you copy what is written, and the site works out the score by period, who got
the game-winning goal, each player's points and penalty minutes, each goalie's record and the standings. If a box
does not add up, the check names it and **nothing is published**.

This page is for whoever types the game files. How the files fit into a season is in `docs/data.md`; this page is
the `sheet:` part. The checks live in `rules.py`; `fixtures/` holds one game for every check below, and the
JavaScript copy of the rules (for the entry page, stage 7) is tested against the same files.

- [The game file](#the-game-file)
- [The boxes](#the-boxes)
- [How the numbers come from it](#how-the-numbers-come-from-it)
- [The game-winning goal and the shutout](#the-game-winning-goal-and-the-shutout)
- [What is checked](#what-is-checked)
- [How to](#how-to): overtime, a shootout, two goalies, a bench penalty, a penalty shot, a spare goalie, a game cut
  short, a forfeit, and the other marks
- [Settings the league may change](#settings-the-league-may-change)
- [What the site shows](#what-the-site-shows)

Words: a game has three **periods**. A tied game may go to **overtime** (OT: usually one sudden-death period, the first
goal wins) and then a **shootout** (SO: shooters one at a time against the goalie). A goal has a scorer and up to two
**assists**; goals plus assists are **points** (PTS). A **penalty** sends a player to the box for some **penalty
minutes** (PIM): 2 for a minor, 4 for a double minor, 5 for a major, 10 for a misconduct. While a team is a player short
the other team is on the **power play** (PP); a goal scored by the short team is **short-handed** (SH). An
**empty-net** goal (EN) is scored while the other team has pulled its goalie. For goalies: **goals against** (GA),
**goals-against average** (GAA, lower is better), **save percentage** (SV%) and a **shutout** (SHO: no goal against).
Pages write shutouts **SHO** because **SO** already means shootout. A **pad** is one sheet of ice and a **week** is one
game night; both live in `schedule.csv` (`date`, `time`, `surface`), not in the game file.

## The game file

The top part is the same for every sport (`game_id`, `status`, `home`, `away`, `scorekeeper`, `checked_by`: see
`docs/data.md`). The sport's part is `sheet:`. Sides are always `home` and `away`, never team ids; "home" only means
the first-listed team (pages say "vs"). Referees' names are not copied: no page shows them.

```yaml
game_id: 2026-11-29-1
status: final
home: blades
away: wolves
scorekeeper: Pat S.
checked_by: Lee M.
sheet:
  roster:                      # who dressed, top to bottom; num is the jersey number written on the sheet
    home:
      - {player: len-t, num: 31}           # the goalie is a roster row too; `goalies` says who played in net
      - {player: barry-s, num: 4}
      - {player: terry-w, num: 6}
      - {player: doug-h, num: 8}
      - {player: gord-p, num: 12}
      - {player: ken-l, num: 17}
    away:
      - {player: murray-b, num: 1}
      - {player: phil-a, num: 2}
      - {player: wayne-k, num: 9}
      - {player: gary-n, num: 11}
      - {player: rod-b, num: 14}
      - {player: bob-c, num: 21}
  goals:                       # the scoring summary, in the order written, both teams
    - {period: 1, time: "4:12", side: home, num: 12, assists: [4, 17]}
    - {period: 1, time: "9:38", side: away, num: 9, assists: [14]}
    - {period: 1, time: "13:05", side: home, num: 17, assists: [12]}
    - {period: 2, time: "2:47", side: away, num: 14, assists: [9, 2]}
    - {period: 2, time: "7:20", side: home, num: 8, assists: [17]}
    - {period: 2, time: "11:54", side: away, num: 9}                  # unassisted: no assists line
    - {period: 3, time: "5:31", side: home, num: 12, assists: [4]}    # the game-winning goal is worked out, never written
    - {period: 3, time: "12:09", side: home, num: 4, assists: [12, 6]}
  penalties:
    - {period: 1, time: "12:15", side: away, num: 21, infraction: Tripping, minutes: 2}
    - {period: 2, time: "9:02", side: home, num: 17, infraction: Hooking, minutes: 2}
    - {period: 3, time: "8:44", side: away, num: 11, infraction: Slashing, minutes: 2}
    - {period: 3, time: "14:10", side: home, num: 8, infraction: Body contact, minutes: 2}
  goalies:                     # each goalie who played, with their goals against
    home: [{num: 31, ga: 3}]
    away: [{num: 1, ga: 5}]
  score:                       # the "score by periods" boxes, as written; ot and so stay empty when not played
    home: {periods: [2, 1, 2], ot: ~, so: ~, final: 5}
    away: {periods: [1, 2, 0], ot: ~, so: ~, final: 3}
```

Blades 5, Wolves 3 (the approved game page). A forfeit has no `sheet` at all: see [A forfeit](#a-forfeit).

**Always put times in quotes** (`"4:12"`). The site's own reader keeps an unquoted `4:12` as text, but other YAML
tools read it as the number 252 (and `12:09` as 729); a time that arrives as a number is an error that says which time
it probably was ("729 looks like 12:09 written without quotes"), and the entry page always writes quotes.

In a **draft** (`drafts/`, never built) any box may be left empty (`~`), and a roster row may be
`{name: Jo K., num: 30}` for a spare who is not in `players.yml` yet.

## The boxes

Rows count from 0 in a problem's path, like list positions: `goals.6` is the **seventh** goal line, `roster.away.4`
the fifth player of the away team, `score.home.periods.1` the home team's second period. A problem's path always
starts with `sheet.` in the message (`sheet.goals.6.time`); the paths below leave that off.

| Box | What goes in it |
|---|---|
| `roster.<side>` | 1 to 25 rows, `{player, num}`: who dressed. `player` is the id from `players.yml`; `num` is the jersey number on the sheet (0 to 99, or `"00"` in quotes), once per team. Every number written elsewhere in the file is looked up here. |
| `goals.<i>` | One line per goal, **both teams in one list**, in the order written. `{period, time, side, num, assists, strength, en, ps}`. |
| `.period` | `1` to the number of periods (`rules.periods`), `OT`, or `OT2`, `OT3`... (only a playoff game played to a first goal has more than one overtime). |
| `.time` | Text like `"4:12"`: minutes, then two digits of seconds. By default **time elapsed in the period**; a league that copies the scoreboard clock sets `rules.clock: remaining`. |
| `.side`, `.num` | `home` or `away`, and the scorer's jersey number (on that team's roster). |
| `.assists` | A list of up to two jersey numbers of the scorer's team, `[4, 17]`. Leave it out for an unassisted goal. |
| `.strength` | `EV` (the default), `PP` (power play) or `SH` (short-handed). Optional. |
| `.en`, `.ps` | `true` for an empty-net goal, `true` for a goal scored on a penalty shot. Optional. |
| `penalties.<i>` | One line per penalty: `{period, time, side, num, infraction, minutes}`. |
| `.num` | The player's jersey number, or `bench` for a bench penalty ([A bench penalty](#a-bench-penalty)). |
| `.served_by` | For a bench penalty: the jersey number of the player who served it. Optional. |
| `.infraction` | Free text, "Tripping". |
| `.minutes` | Penalty minutes, a whole number from 1 to 20 (2, 4, 5 and 10 are the usual ones). |
| `goalies.<side>` | One goalie row `{num, ga}`, or two when both played. |
| `.ga` | Goals against: required. Empty-net goals are not charged to a goalie. |
| `.shots` | Shots against, only when `rules.goalie_shots` is `recorded`. |
| `.decision` | `true` on the goalie who gets the win or loss, **only** when a team used two goalies. |
| `shootout` | Only after a game still level after overtime: `{first, home: [...], away: [...]}`, each shot `{num, scored}`. |
| `score.<side>` | `{periods, ot, so, final}`: the score-by-periods boxes as written. `periods` has one number per period; `ot` is the overtime goals (only when overtime was played; `0` for a scoreless one); `so` is `1` for the shootout winner and `0` for the other team (only after a shootout); `final` is the Final box. They must agree with the goal lines. |

## How the numbers come from it

Goals are first put in **time order within each period**, so the running score and the game-winning goal follow the
game and not the order of the lines.

| Number | From |
|---|---|
| Score by period | The goal lines per regulation period (the boxes must agree). |
| Final score | The periods plus overtime plus the shootout (the Final box must agree). A shootout win adds one goal to the winner, which counts in goals for and against and the goal difference. |
| Decided in | `overtime` after an overtime goal, `shootout` after a shootout, else regulation. A game still level after overtime is a tie. |
| Goals, assists, points | Goals and assists from the goal lines; points are goals plus assists. A shootout goal is nobody's goal and nobody's point. |
| PPG, SHG | The player's goals marked `PP` and `SH`. Shown in a player's season totals, not in the game tables. |
| PIM | The penalty's minutes, to the player. A bench penalty counts to nobody; the team total in the foot of the game page includes it. |
| Games played | One for every roster row that has a player id. A goalie who played gets a **goalie** game, everyone else (a goalie who did not play too) a **skater** game. |
| Goalie record | The goalie of record (the only goalie of the team, or the one with `decision: true`) gets the win, the loss or the tie. An overtime or shootout loss is a loss, and also an **OTL** (OTL is "of the losses", as in the standings). |
| Goals against (GA) | The goalie's `ga` box. A shootout goal is not a goal against. |
| GAA | Goals against per game played (a game sheet has no minutes in net), so a goalie relieved early still gets a full game. |
| SV% | (shots - GA) / shots, only for goalies whose games recorded shots. |
| Goalie assists and PIM | A goalie's own assists and penalty minutes count to the goalie, who is listed with the skaters on the game page when there are any. |

Goalies and skaters are two **stat groups**: skaters have GP, G, A, PTS, PIM (and PPG, SHG, GWG in the season totals);
goalies have GP, W, L, T, GA, GAA, SHO and SV% (and OTL, A, PIM in the season totals). A player with games in both has
both.

## The game-winning goal and the shutout

**The game-winning goal (GWG)** is the goal that put the winner one goal ahead of the loser's final total: the winning
team's (loser's goals + 1)th goal, in time order, overtime and empty-net goals included. There is no GWG after a tie or
a shootout (the shootout goal belongs to nobody). It is worked out, never written, so it cannot disagree with the goal
lines.

**A shutout (SHO)** goes to a goalie who played the **whole game alone** (the team has one goalie row) and whose team
allowed **no goal at all in the periods or overtime**, empty-net goals included. A shutout shared by two goalies is not
credited. The shootout is ignored: a goalie who lets in no goal in the periods and overtime and then loses a shootout
still has the shutout.

## What is checked

Every problem has a path (the box), a level, and one sentence that says what to do. An **error** stops the build. A
**warning** is shown and never stops it. A **gap** is an empty box: an error in `games/`, a warning in `drafts/`, so a
draft is never stricter than a finished file. Unknown lines are errors at every level, because they are nearly always
typos. Paths below are relative to `sheet`; `<side>` is `home` or `away`, `<i>` counts from 0.

| Path | What is wrong | Level |
|---|---|---|
| `<key>` | a line other than `roster goals penalties goalies shootout score` | error |
| `""` (the whole sheet) | not a block | error |
| `roster` | missing | gap |
| `roster` | not a block | error |
| `roster.zzz` | a side that is not `home` or `away` | error |
| `roster.<side>` | missing | gap |
| `roster.<side>` | not a list of 1 to 25 rows | error |
| `roster.<side>.<i>` | not a row; an unknown key (`.<key>`) | error |
| `roster.<side>.<i>.num` | missing; not 0 to 99 or `"00"`; the same number twice on a team | error |
| `roster.<side>.<i>.player` | missing (a row with only a `name`: a spare not yet in `players.yml`) | gap |
| `roster.<side>.<i>.player` | not in `players.yml`; listed twice in the game | error |
| `roster.<side>.<i>.player` | on another team and not `sub: true` | warning |
| `goals` | not a list (a missing `goals` is a game with no goals) | error |
| `goals.<i>` | not a row; an unknown key (`.<key>`) | error |
| `goals.<i>.period` | missing | gap |
| `goals.<i>.period` | not `1` to `rules.periods`, `OT`, or `OT2`...; `OT2` and later outside a playoff game with sudden-death overtime | error |
| `goals.<i>.time` | missing | gap |
| `goals.<i>.time` | not text like `"4:12"` (a number: "write it in quotes"); past the end of the period (`rules.period_minutes`, `rules.overtime_minutes` in overtime) | error |
| `goals.<i>.time` | out of order with the line before it in the same period (with the league's clock direction) | warning |
| `goals.<i>.side` | missing | gap |
| `goals.<i>.side` | not `home` or `away` | error |
| `goals.<i>.num` | missing | gap |
| `goals.<i>.num` | not a jersey number; not on that team's roster | error |
| `goals.<i>.assists` | not a list; more than two | error |
| `goals.<i>.assists.<j>` | not a jersey number; not on the scorer's roster; the scorer; the same player twice | error |
| `goals.<i>.strength` | not `EV`, `PP` or `SH` | error |
| `goals.<i>.en`, `.ps` | not `true` | error |
| `goals.<i>.assists` | a penalty-shot goal (`ps: true`) with assists | error |
| `goals.<i>.strength` | `PP` and the other team has no penalty in this period or the one before; `SH` and this team has none ("check the strength mark") | warning |
| `goals.<i>.num` | a player with more goals than `rules.goal_cap` (when it is set), reported at the goal that passes it | warning |
| `penalties` | not a list (a missing `penalties` is a game with none) | error |
| `penalties.<i>` | not a row; an unknown key (`.<key>`) | error |
| `penalties.<i>.period`, `.time`, `.side` | missing | gap |
| `penalties.<i>.period`, `.time`, `.side` | wrong, as for goals (`OT2` and later only in a playoff game with sudden-death overtime) | error |
| `penalties.<i>.time` | out of order with the line before it in the same period | warning |
| `penalties.<i>.num` | missing | gap |
| `penalties.<i>.num` | not a jersey number on the roster and not `bench` | error |
| `penalties.<i>.served_by` | set without `num: bench`; not on the roster | error |
| `penalties.<i>.infraction` | missing | gap |
| `penalties.<i>.infraction` | not text | error |
| `penalties.<i>.minutes` | missing | gap |
| `penalties.<i>.minutes` | not a whole number from 1 to 20 | error |
| `penalties.<i>.minutes` | not 2, 4, 5 or 10 ("unusual: check the sheet") | warning |
| `goalies` | missing | gap |
| `goalies` | not a block | error |
| `goalies.zzz` | a side that is not `home` or `away` | error |
| `goalies.<side>` | missing | gap |
| `goalies.<side>` | not a list of 1 or 2 rows | error |
| `goalies.<side>.<i>` | not a row; an unknown key (`.<key>`) | error |
| `goalies.<side>.<i>.num` | missing | gap |
| `goalies.<side>.<i>.num` | not on that team's roster; the same goalie twice | error |
| `goalies.<side>.<i>.ga` | missing | gap |
| `goalies.<side>.<i>.ga` | not a whole number from 0 | error |
| `goalies.<side>` | the GA boxes add up to something other than the other team's goals in the periods and overtime, empty-net goals left out ("the GA boxes add up to 4, but Wolves scored 5, none into an empty net") | error |
| `goalies.<side>.<i>.shots` | set when `rules.goalie_shots` is `none`; not a whole number; less than the goalie's `ga` | error |
| `goalies.<side>.<i>.shots` | missing when `rules.goalie_shots` is `recorded` | gap |
| `goalies.<side>` | two goalies and no `decision: true` ("who gets the win or loss?") | gap |
| `goalies.<side>` | two goalies and more than one `decision: true` | error |
| `goalies.<side>.<i>.decision` | not `true` (or left out) | error |
| `goalies.<side>.0.decision` | `decision: true` for a team with one goalie | warning |
| `score` | missing | gap |
| `score` | not a block | error |
| `score.zzz` | a side that is not `home` or `away` | error |
| `score.<side>` | missing; `periods` or `final` missing | gap |
| `score.<side>` | not a block; an unknown box (`.<key>`) | error |
| `score.<side>.periods` | not a list of `rules.periods` whole numbers | error |
| `score.<side>.periods.<i>` | empty | gap |
| `score.<side>.periods.<i>` | not a whole number; not the side's goals in that period ("the box says 2, but the goal lines have 1") | error |
| `score.<side>.ot` | not a whole number, or filled although regulation was not level, or this league plays no overtime in this kind of game (`rules.overtime`, `rules.playoff_overtime`) | error |
| `score.<side>.ot` | empty although regulation was level and overtime is played here ("write 0 for a scoreless overtime") | gap |
| `score.<side>.ot` | not the side's goals in overtime | error |
| `goals.<i>.period` | an overtime goal although there is no overtime in this game; a second overtime goal (overtime is sudden death: the first goal ends it) | error |
| `shootout` | filled although the game was not level after overtime, or this league plays no shootout here | error |
| `shootout` | missing although it was level after overtime and a shootout is played here | gap |
| `shootout` | not a block; an unknown key (`.<key>`) | error |
| `shootout.first` | missing | gap |
| `shootout.first` | not `home` or `away` | error |
| `shootout.<side>` | missing | gap |
| `shootout.<side>` | not a list | error |
| `shootout.<side>.<i>` | not a row; an unknown key (`.<key>`) | error |
| `shootout.<side>.<i>.num` | not on the roster | error |
| `shootout.<side>.<i>.scored` | missing | gap |
| `shootout.<side>.<i>.scored` | not `true` or `false` | error |
| `shootout` | level at the end ("a shootout ends with a winner") | error |
| `shootout` | shots that do not fit `rules.shootout_rounds`: a round missing, or shots after it was decided | warning |
| `score.<side>.so` | filled although there was no shootout in this game; not 0 or 1; not 1 for the shootout winner and 0 for the other team | error |
| `score.<side>.so` | empty although a shootout was played | gap |
| `score.<side>.final` | missing | gap |
| `score.<side>.final` | not a whole number; not the periods plus overtime plus shootout ("the Final box says 6, but the periods, overtime and shootout add up to 5") | error |

After these the core adds one more, at `score.home.final` (the Final box of the first-listed team): a **tied playoff
game**, and a **tied regular-season game when `standings.ties` is false**.

When a box makes the later checks meaningless, checking stops there instead of listing a cascade: with no `roster` a
team's numbers are not looked up; with a goal line that has no period or side, the score boxes, the overtime checks
and the GA totals are not compared with the goals; with no usable `score`, there are no score checks.

The checks that look at the whole file (`game_id` against the file name and the schedule, `status` against the folder,
`home` and `away` against the schedule, `checked_by`, `forfeit`) are the core's: see `docs/data.md`.

## How to

### Overtime

What happens to a game still level after the last period is the league's setting (`rules.overtime` for the regular
season, `rules.playoff_overtime` for the playoffs):

* `none` (the default, shown as `[placeholder]`): a regular-season game that is level is a **tie**. Write nothing.
* `overtime`: one sudden-death overtime (`rules.overtime_minutes`, 5). If nobody scores it is still a tie.
* `shootout`: the overtime, then a shootout if nobody scores.
* `shootout_only`: straight to the shootout after the last period (the OT boxes stay empty).
* A **playoff** game level after the last period always goes on: `sudden_death` plays overtime periods until a goal,
  `shootout` plays one overtime and then a shootout.

Write the overtime goals as goal lines with `period: OT`, and fill in the `ot` boxes of **both** teams (0 and 0 for a
scoreless overtime):

```yaml
  goals:
    - ...
    - {period: OT, time: "2:10", side: home, num: 12, assists: [4]}      # time in the overtime period
  score:                       # 2-2 after three periods; Gord P. wins it in overtime
    home: {periods: [1, 0, 1], ot: 1, so: ~, final: 3}
    away: {periods: [0, 1, 1], ot: 0, so: ~, final: 2}
```

Overtime is sudden death: only one overtime goal is possible. When a playoff overtime takes more than one period, the
goal is written `period: OT2` (or `OT3`), and the single `ot` box still holds the total. The game page shows an `OT`
column and "Final · OT". An overtime win and loss are a win and a loss in the standings unless the league pays for the
loss (`standings.points.ot_loss: 1`; add `otl` to the columns).

### A shootout

Only after a game still level after overtime (or straight after the last period with `shootout_only`). Fill in who
shot first (`first` decides when a shootout can stop early), each team's shooters in the order they shot, and
`so: 1` for the winner and `0` for the other team:

```yaml
  shootout:
    first: home
    home: [{num: 12, scored: true}, {num: 8, scored: false}, {num: 4, scored: true}]
    away: [{num: 9, scored: false}, {num: 14, scored: true}, {num: 2, scored: false}]
  score:                       # 2-2 after three, a scoreless OT, Alpha wins the shootout 2-1
    home: {periods: [1, 0, 1], ot: 0, so: 1, final: 3}
    away: {periods: [0, 1, 1], ot: 0, so: 0, final: 2}
```

The shootout winner gets **one goal** in the final score (3-2), which counts in goals for, goals against and the goal
difference. No player gets a goal or a point and no goalie a goal against. A shootout is three rounds each
(`rules.shootout_rounds`), then one round at a time until a round is not level; it stops early when one team cannot be
caught. Shots after that point, or a missing round, are warnings. The game page says "Won in a shootout" and shows the
shots under "Shootout".

### Two goalies

When a team used two goalies, list both, each with the goals against **while in net**, and mark the one who gets
the win or the loss with `decision: true`:

```yaml
  goalies:
    home: [{num: 31, ga: 2}, {num: 35, ga: 1, decision: true}]    # Len T. started, Stu G. finished and took the win
```

Both get a game played and their own goals against; only the one with the decision gets the win, loss or tie, and a
shutout is not credited to either. With two goalies `decision` is required; with one it is not needed (marking it is a
warning).

### A bench penalty

A penalty to the team, not a player (too many players, delay of game): `num: bench`, and optionally who served it:

```yaml
    - {period: 2, time: "5:10", side: home, num: bench, served_by: 6, infraction: Too many players, minutes: 2}
```

It counts to **nobody's** PIM; the team's PIM in the foot of the game page includes it. `served_by` is only allowed with
`bench`, and the number must be on the roster.

### A penalty shot

A goal scored on a penalty shot is a goal line with `ps: true` and **no assists**:

```yaml
    - {period: 2, time: "3:02", side: away, num: 11, ps: true}
```

It counts as a goal against the goalie (the GA boxes include it) and the game page marks it "(PS)". A missed penalty
shot is not recorded. Other marks work the same way: `strength: PP` or `SH` after a power play or a short-handed goal
(a warning if the other team has no penalty in that period or the one before), and `en: true` for a goal into an empty
net, which is **not** charged to the goalie: the GA boxes then add up to the other team's goals minus the empty-net
ones.

### A spare goalie

A goalie who is not on the team's roster that night is a spare, as in any sport:

1. Add the spare to `players.yml` first: `{id: stu-g, name: Stu G., team: null, sub: true}` (a spare who belongs to no team).
2. Put them on the roster with their jersey number, and in `goalies`: `{player: stu-g, num: 35}` in `roster`, `{num: 35, ga: 1}` in
   `goalies`.

A regular player of another team who fills in is already in `players.yml`: mark them `sub: true` there, or the check
warns you (`... is not on <team>`). A warning never stops the build. If you are typing the file before you know who the
spare is, write the row as it is on paper, `{name: Jo K., num: 30}`, and save it as a **draft**; a finished file cannot
have such a row. A goalie who dressed but did not play is a roster row and gets a skater game with no stats: leave them
off the roster if you do not want that.

### A game cut short

If ice time ran out or a mercy rule ended the game early, the **score stands as written**. Copy the boxes and the goal
lines as they are, and say why in the envelope's `notes`:

```yaml
notes: Stopped after 2 periods, 7 goals ahead (mercy rule).
```

There is no special key and no special display: the game page shows the score and the periods that were played. A
league that caps the goal difference for the standings uses `standings.tiebreakers: [wins, head_to_head, {diff: {cap: 5}}]`.
A period that was never played is written as `0` in the period boxes (and has no goal lines).

### A forfeit

A forfeit has no sheet. The game file names the team that forfeited and leaves `sheet:` out:

```yaml
game_id: 2026-12-08-2
status: final
home: blades
away: wolves
checked_by: Lee M.
forfeit: wolves
```

No player gets a game played and no goalie a decision. How the score counts (default: 1 to 0, shown as
`[placeholder]`) is the league's to decide under `standings: forfeit:` in `league.yml`; `{score: [5, 0]}` is common.

## Settings the league may change

Set in `league.yml` under `rules:`, `standings:` and `stats.minimums:`; each one marked *decide* shows as
`[placeholder]` on the site, and in the build's "Still to decide" list, until the league sets it (even to the usual
value).

| Setting | Values | Default |
|---|---|---|
| `rules.periods` | 2 to 4: periods in a game (a game file has exactly that many boxes) | 3 (*decide*) |
| `rules.period_minutes` | 5 to 30: only drives the time check | 15 (*decide*) |
| `rules.overtime` | `none`, `overtime`, `shootout`, `shootout_only`: a regular-season game level after the last period | `none` (*decide*) |
| `rules.playoff_overtime` | `sudden_death`, `shootout`: a playoff game level after the last period | `sudden_death` (*decide*) |
| `rules.overtime_minutes` | 1 to 20: only drives the time check in overtime | 5 (*decide*) |
| `rules.shootout_rounds` | 1 to 5: shooters each before sudden death; only drives the shootout warning | 3 (*decide*) |
| `rules.clock` | `elapsed`, `remaining`: whether times are time elapsed or time left in the period. A wrong setting puts the goals of a period in the wrong order, which changes the running score and can pick the wrong winning goal, so set it | `elapsed` (*decide*) |
| `rules.goalie_shots` | `none`, `recorded`: whether the sheet has shots against; SV% and its board appear only when recorded | `none` |
| `rules.goal_cap` | 0 to 10: most goals one player may score in a game; 0 is no cap; passing it is a warning | 0 (*decide*) |
| `stats.minimums.goalie_min_games` | games a goalie needs to rank on GAA and SV% (never more than the team has played) | 4 (*decide*) |
| `standings.points` | `{win, tie, loss, ot_win, ot_loss}` | 2, 1, 0 (an overtime or shootout win and loss count as a win and a loss) |
| `standings.ties` | `true`, `false` | `true` (*decide*). A league that never allows ties sets `ties: false` **and** `overtime: shootout` |
| `standings.forfeit` | `{score: [1, 0]}`, `{score: [5, 0]}` | `[1, 0]` (*decide*) |
| `standings.tiebreakers` | `wins`, `head_to_head`, `diff`, `points_for`, ... `{diff: {cap: 5}}` caps each game's margin | wins, head-to-head, goal difference (*decide*) |
| `standings.columns` | `gp w l t otl pts pf pa diff ...` | `gp w l t pts pf pa` |

Common variants:

```yaml
rules: {overtime: shootout}                                       # a level regular-season game goes to a shootout
standings: {ties: false, points: {ot_loss: 1}, columns: [gp, w, l, otl, pts, pf, pa]}   # no ties, a point for the OT loss
rules: {goalie_shots: recorded}                                   # shots against on the sheet: SV% appears
rules: {periods: 2, period_minutes: 25}                           # two 25-minute halves
rules: {clock: remaining}                                         # times copied from the scoreboard clock
standings: {tiebreakers: [wins, head_to_head, {diff: {cap: 5}}]} # a mercy-rule league
```

A league that names three stars or limits a player's penalties before ejection can write them in `notes`: neither is
a setting.

## What the site shows

* **Game page:** the final panel with the periods (and `OT`, `SO` columns when played), the goalies and the penalty
  minutes under the line score; "Scoring" with a group per period (the tally, each goal with its assists, GWG badge and
  the running score, and "No scoring" for a period with none); "Penalties"; "Goalies" with each goalie's result and
  goals against (and shots and SV% when recorded); "Skaters" with G, A, PTS and PIM of everyone with a goal, assist or
  penalty.
* **Standings:** GP W L T PTS GF GA.
* **Stats:** a Skaters table and a Goalies table, and leaders for points, goals, assists, penalty minutes, goals-against
  average (lowest first), shutouts and save percentage (when shots are recorded). Goalies need `goalie_min_games` games
  to rank. Technical details such as PPG, SHG and GWG are in a player's season totals.
* **Players** are shown as "First L." with their jersey number from `players.yml`; no full names, contact details or photos.
