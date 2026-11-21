# Hockey fixtures

One game file per case, with what the rules must say about it. They are shared: `tests/test_hockey_fixtures.py`
runs them against `rules.py`, and the JavaScript copy of the rules (stage 7, for the entry page) is tested against the
same files.

| File | What it is |
|---|---|
| `context.yml` | The teams (Alpha `aa` is "home", Bravo `bb` is "away", Charlie `cc` plays in neither), the players with their jersey numbers (a spare goalie with `sub: true`, a player of the third team), and the league settings every case is checked with (the sport's defaults). All made up. |
| `<name>.yml` | One case. `fixture: {folder, game_type, options}` says where the file lives (`games` or `drafts`), whether it is a `regular` or `playoff` game, and any rules that differ from `context.yml` (`overtime`, `clock`, `goalie_shots`...). `sheet:` is the sport's part of the game file. A comment at the top says what the case shows. |
| `<name>.expected.json` | `problems`: every problem `check` must return, in order, as `{level, at, message}` (the path is relative to `sheet`; the core adds `sheet.`). `reading`: what `read` returns as `{score, lines, team_lines, facts}`, or `null` when `check` reports an error, or a draft leaves out a box (a roster row with only a `name` still reads: that row has no line). `score.final_at` is the one path that starts with `sheet.`: it is from the top of the file. |

Every row of the checks table in `../README.md` has a case; `tests/test_hockey_fixtures.py` lists which (`ROWS`). The
cases that should be quiet are `QUIET` there.

**Changing a rule.** Edit `rules.py`, then `UPDATE_FIXTURES=1 python -m pytest tests/test_hockey_fixtures.py`
rewrites the expected files. Read the diff: every changed line is a change in what the rules say. A new check gets a
new case.

**For the JavaScript runner.** Empty boxes are `~` (null). Times are quoted text (`"4:12"`); the two cases that show
the YAML trap (`time-unquoted`, `penalty-time-unquoted`) hold the number a plain YAML reader makes of an unquoted time
(729, 850), so both readers see the same file. A case whose header says `python_only: true` in its `fixture:` block is
for the Python reader alone (there is none today). `num` is a number, or the text `"00"`. A message that prints a
Python `repr` of a text value (`'abc'`, in single quotes) must print the same text. The `facts` of a reading keep a
goal's `period` as written (`1`, `"OT"`, `"OT2"`).
