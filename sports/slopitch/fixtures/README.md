# Slo-pitch fixtures

One game file per case, with what the rules must say about it. They are shared: `tests/test_slopitch_fixtures.py`
runs them against `rules.py`, and the JavaScript copy of the rules (stage 7, for the entry page) is tested against the
same files.

| File | What it is |
|---|---|
| `context.yml` | The teams (Alpha `aa` is "home", the team that bats last, Bravo `bb` is "away", Charlie `cc` plays in neither), the players (ten batters each, a spare with `sub: true`, a player of the third team) and the league settings every case is checked with (the sport's defaults). All made up. |
| `<name>.yml` | One case. `fixture: {folder, game_type, options}` says where the file lives (`games` or `drafts`), whether it is a `regular` or `playoff` game, and any rules that differ from `context.yml` (`limit_play`, `batting`, `extra_innings`...). `sheet:` is the sport's part of the game file. A comment at the top says what the case shows. |
| `<name>.expected.json` | `problems`: every problem `check` must return, in order, as `{level, at, message}` (the path is relative to `sheet`; the core adds `sheet.`). `reading`: what `read` returns as `{score, lines, team_lines, facts}`, or `null` when `check` reports an error, or a draft leaves out a box (a batting row with only a `name` still reads: that row has no player and no game). `score.final_at` is the one path that starts with `sheet.`: it is from the top of the file. |

Every row of the checks table in `../README.md` has a case; `tests/test_slopitch_fixtures.py` lists which (`ROWS`). The
cases that should be quiet are `QUIET` there. `clean` is the approved Slopitch-Game mockup (Bravo 11 at Alpha 14);
most other cases are the same game or a game with no batting lines (the order and the H boxes only) with one thing
changed.

**Changing a rule.** Edit `rules.py`, then `UPDATE_FIXTURES=1 python -m pytest tests/test_slopitch_fixtures.py`
rewrites the expected files. Read the diff: every changed line is a change in what the rules say. A new check gets a
new case.

**For the JavaScript runner.** Empty boxes are `~` (null). `X` is the text `"X"`. A run box that is `true` in YAML
(`run-box-true`) reads as a boolean and is an error, not a number. A message that prints a Python `repr` of a value
(`'three'`, `True`) must print the same text. The `facts` of a reading keep each side's runs with `null` for an `X` or
an inning a called game never reached; `Score.extra` holds `0` for an `X` in an extra inning (it cannot hold `null`).
