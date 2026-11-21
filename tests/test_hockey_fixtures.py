"""The hockey fixtures (sports/hockey/fixtures/, docs/stage-5-hockey-spec.md section 8): one game file per case,
the problems `check` must report (level, path, message, in order) and the numbers `read` must give.

Each case is `<name>.yml` (`fixture: {folder, game_type, options}` and `sheet:`) with `<name>.expected.json`
(`problems`, and `reading`: null when there is an error or a draft leaves out a box, else score, lines and facts).
`context.yml` holds the teams, the players and the league settings they are checked with. The stage 7 JavaScript
rules are tested against the same files (a case marked `python_only` is for Python alone). `UPDATE_FIXTURES=1 python
-m pytest tests/test_hockey_fixtures.py` rewrites the expected files; read the diff before committing it.
"""
import copy
import json
import os
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from scripts.core.model import Player, SportContext, Team
from scripts.core.problems import call_sport, parse_yaml
from scripts.core.sports import SPORTS_ROOT, load_sport

FIXTURES = Path(__file__).resolve().parent.parent / "sports" / "hockey" / "fixtures"
CASES = sorted(p.name[:-len(".yml")] for p in FIXTURES.glob("*.yml") if p.name != "context.yml")
UPDATE = bool(os.environ.get("UPDATE_FIXTURES"))

SPORT, LOAD_PROBLEMS = load_sport("hockey", SPORTS_ROOT)


def load_context():
    raw = parse_yaml((FIXTURES / "context.yml").read_text(encoding="utf-8"))
    teams = {t["id"]: Team(t["id"], t["name"], t["code"]) for t in raw["teams"]}
    players = {p["id"]: Player(p["id"], p["name"], p["team"], p.get("number"), p.get("sub", False), p.get("position"))
               for p in raw["players"]}
    return raw, teams, players


def load_case(name):
    return parse_yaml((FIXTURES / f"{name}.yml").read_text(encoding="utf-8"))


def context_for(case):
    raw, teams, players = load_context()
    fixture = case["fixture"]
    defaults = {key: opt["default"] for key, opt in SPORT.spec["options"].items()}
    options = {**defaults, **raw["options"], **fixture["options"]}
    return SportContext(sport=SPORT.spec, options=options, teams=teams, players=players, sides=raw["sides"],
                        game_type=fixture["game_type"], folder=fixture["folder"])


def readable(sheet, ctx):
    """`read` is for a sheet `check` accepted. A draft reads when it has no error and, written as a finished file,
    its only errors are roster rows with no player id yet (a spare written in by name)."""
    if any(p.level == "error" for p in SPORT.rules.check(sheet, ctx)):
        return False
    final = [p for p in SPORT.rules.check(sheet, replace(ctx, folder="games")) if p.level == "error"]
    return all(p.at.startswith("roster.") and p.at.endswith(".player") for p in final)


def run(name):
    """(problems as dicts, reading as a dict or None) for one case, through call_sport so the shapes are checked too."""
    case = load_case(name)
    ctx = context_for(case)
    problems = call_sport("check", SPORT.rules.check, case["sheet"], ctx)
    result = [{"level": p.level, "at": p.at, "message": p.message} for p in problems]
    reading = None
    if readable(case["sheet"], ctx):
        read = call_sport("read", SPORT.rules.read, case["sheet"], ctx)
        reading = {"score": asdict(read.score), "lines": [asdict(ln) for ln in read.lines], "team_lines": read.team_lines,
                   "facts": read.facts}
    return result, reading


def expected_text(problems, reading):
    return json.dumps({"problems": problems, "reading": reading}, indent=2, ensure_ascii=False) + "\n"


def test_the_sport_loads_and_has_its_fixtures():
    assert not [p for p in LOAD_PROBLEMS if p.level == "error"], LOAD_PROBLEMS
    assert len(CASES) >= 70
    assert (FIXTURES / "context.yml").is_file()


def test_every_case_has_an_expected_file_and_no_expected_file_is_left_over():
    expected = {p.name[:-len(".expected.json")] for p in FIXTURES.glob("*.expected.json")}
    if UPDATE:
        return
    assert expected == set(CASES)


@pytest.mark.parametrize("name", CASES)
def test_fixture(name):
    problems, reading = run(name)
    path = FIXTURES / f"{name}.expected.json"
    if UPDATE:
        path.write_text(expected_text(problems, reading), encoding="utf-8")
        return
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert problems == expected["problems"]
    assert reading == expected["reading"]


# ------------------------------------------------------------------ every row of the spec's table 3.1

# (what the row checks, the case, level, path): the case's expected problems must hold that level and path.
ROWS = [
    ("a key other than roster goals penalties goalies shootout score", "unknown-keys", "error", "referee"),
    ("the sheet is not a block", "not-a-block", "error", ""),
    ("roster missing", "roster-missing", "error", "roster"),
    ("roster missing, in a draft", "roster-missing-draft", "warning", "roster"),
    ("roster not a block", "roster-not-a-block", "error", "roster"),
    ("roster: an unknown side", "roster-unknown-side", "error", "roster.zzz"),
    ("roster.<side> missing", "roster-one-side", "error", "roster.away"),
    ("roster.<side> an empty list", "roster-empty-list", "error", "roster.home"),
    ("roster.<side> more than 25 rows", "roster-too-many", "error", "roster.home"),
    ("roster.<side>.<i> not a row", "roster-row-not-a-block", "error", "roster.home.2"),
    ("roster.<side>.<i> an unknown key", "roster-unknown-key", "error", "roster.home.2.pos"),
    ("num missing", "roster-num-missing", "error", "roster.home.2.num"),
    ("num above 99", "roster-num-too-big", "error", "roster.home.2.num"),
    ("num written as text (not \"00\")", "roster-num-text", "error", "roster.home.2.num"),
    ("num twice on one side", "roster-dup-number", "error", "roster.home.3.num"),
    ("player missing (a name only), final file", "name-in-final", "error", "roster.home.2.player"),
    ("player missing (a name only), draft", "draft-with-name", "warning", "roster.home.2.player"),
    ("player not in players.yml", "player-unknown", "error", "roster.home.2.player"),
    ("player listed twice", "player-twice", "error", "roster.home.3.player"),
    ("player on another team and not a spare", "spare-other-team", "warning", "roster.home.2.player"),
    ("goals not a list", "goals-not-a-list", "error", "goals"),
    ("goals.<i> not a row", "goal-row-not-a-block", "error", "goals.7"),
    ("goals.<i> an unknown key", "goal-unknown-key", "error", "goals.7.ref"),
    ("period not 1 to periods, OT or OT2...", "goal-period-bad", "error", "goals.7.period"),
    ("period missing", "goal-period-missing", "error", "goals.7.period"),
    ("period missing, in a draft", "goal-period-missing-draft", "warning", "goals.7.period"),
    ("OT2 outside a playoff sudden-death game", "goal-ot2-regular", "error", "goals.4.period"),
    ("time missing", "time-missing", "error", "goals.7.time"),
    ("time not text (put the time in quotes)", "time-unquoted", "error", "goals.7.time"),
    ("time not like 4:12", "time-not-a-time", "error", "goals.7.time"),
    ("time past the period's length", "time-past-period", "error", "goals.7.time"),
    ("time past the overtime's length", "time-past-ot", "error", "goals.4.time"),
    ("time out of order (elapsed clock)", "time-out-of-order", "warning", "goals.1.time"),
    ("time out of order (remaining clock)", "time-out-of-order-remaining", "warning", "goals.1.time"),
    ("side missing", "side-missing", "error", "goals.7.side"),
    ("side not home or away", "side-bad", "error", "goals.7.side"),
    ("num missing", "scorer-missing", "error", "goals.7.num"),
    ("num not on that side's roster", "scorer-not-on-roster", "error", "goals.7.num"),
    ("num on the other team's roster", "scorer-wrong-team", "error", "goals.7.num"),
    ("assists not a list", "assists-not-a-list", "error", "goals.7.assists"),
    ("more than two assists", "three-assists", "error", "goals.7.assists"),
    ("an assist not on the scorer's roster", "assist-not-on-roster", "error", "goals.7.assists.1"),
    ("an assist that is not a number", "assist-bad-number", "error", "goals.7.assists.1"),
    ("the scorer as an assist", "assist-is-scorer", "error", "goals.7.assists.1"),
    ("the same assist twice", "assist-twice", "error", "goals.7.assists.1"),
    ("strength not EV, PP or SH", "strength-bad", "error", "goals.7.strength"),
    ("en not true", "en-not-true", "error", "goals.7.en"),
    ("ps not true", "ps-not-true", "error", "goals.7.ps"),
    ("ps with assists", "ps-with-assist", "error", "goals.3.assists"),
    ("PP and the other team has no penalty", "pp-without-penalty", "warning", "goals.0.strength"),
    ("SH and this team has no penalty", "sh-without-penalty", "warning", "goals.0.strength"),
    ("more goals than goal_cap", "goal-cap", "warning", "goals.6.num"),
    ("penalties not a list", "penalties-not-a-list", "error", "penalties"),
    ("penalties.<i> not a row", "penalty-row-not-a-block", "error", "penalties.3"),
    ("penalties.<i> an unknown key", "penalty-unknown-key", "error", "penalties.3.ref"),
    ("penalty period missing", "penalty-period-missing", "error", "penalties.3.period"),
    ("penalty in OT2 outside a playoff sudden-death game", "penalty-ot2-regular", "error", "penalties.4.period"),
    ("penalty time not text", "penalty-time-unquoted", "error", "penalties.3.time"),
    ("penalty time past the period's length", "penalty-time-past-period", "error", "penalties.3.time"),
    ("penalty side not home or away", "penalty-side-bad", "error", "penalties.3.side"),
    ("penalty time out of order", "penalty-time-out-of-order", "warning", "penalties.3.time"),
    ("penalty num missing", "penalty-num-missing", "error", "penalties.3.num"),
    ("penalty num not on the roster and not bench", "penalty-not-on-roster", "error", "penalties.3.num"),
    ("served_by without bench", "served-by-without-bench", "error", "penalties.3.served_by"),
    ("served_by not on the roster", "served-by-not-on-roster", "error", "penalties.4.served_by"),
    ("infraction missing", "infraction-missing", "error", "penalties.3.infraction"),
    ("infraction not text", "infraction-not-text", "error", "penalties.3.infraction"),
    ("minutes missing", "minutes-missing", "error", "penalties.3.minutes"),
    ("minutes not a whole number from 1 to 20", "minutes-bad", "error", "penalties.3.minutes"),
    ("minutes written as a word", "minutes-text", "error", "penalties.3.minutes"),
    ("minutes not 2, 4, 5 or 10", "odd-minutes", "warning", "penalties.3.minutes"),
    ("goalies missing", "goalies-missing", "error", "goalies"),
    ("goalies missing, in a draft", "no-goalies-draft", "warning", "goalies"),
    ("goalies not a block", "goalies-not-a-block", "error", "goalies"),
    ("goalies: an unknown side", "goalies-unknown-side", "error", "goalies.zzz"),
    ("goalies.<side> missing", "goalies-side-missing", "error", "goalies.away"),
    ("goalies.<side> an empty list", "goalies-empty-list", "error", "goalies.home"),
    ("goalies.<side> three rows", "goalies-three", "error", "goalies.home"),
    ("goalies.<side>.<i> not a row", "goalie-row-not-a-block", "error", "goalies.home.0"),
    ("goalies.<side>.<i> an unknown key", "goalie-unknown-key", "error", "goalies.home.0.saves"),
    ("goalie num missing", "goalie-num-missing", "error", "goalies.home.0.num"),
    ("goalie num not on that side's roster", "goalie-not-on-roster", "error", "goalies.home.0.num"),
    ("goalie num twice", "goalie-twice", "error", "goalies.home.1.num"),
    ("ga missing", "ga-missing", "error", "goalies.home.0.ga"),
    ("ga not a whole number from 0", "ga-negative", "error", "goalies.home.0.ga"),
    ("the goalies' ga not the other team's goals (home)", "ga-mismatch", "error", "goalies.home"),
    ("the goalies' ga not the other team's goals (away)", "ga-mismatch-away", "error", "goalies.away"),
    ("an empty-net goal not marked en", "en-goal-not-marked", "error", "goalies.away"),
    ("shots set when goalie_shots is none", "shots-when-none", "error", "goalies.home.0.shots"),
    ("shots missing when recorded", "shots-missing", "error", "goalies.away.0.shots"),
    ("shots not a whole number", "shots-bad", "error", "goalies.home.0.shots"),
    ("shots less than ga", "shots-below-ga", "error", "goalies.home.0.shots"),
    ("two goalies and no decision", "two-goalies-no-decision", "error", "goalies.home"),
    ("two goalies and no decision, in a draft", "two-goalies-no-decision-draft", "warning", "goalies.home"),
    ("two goalies and two decisions", "two-decisions", "error", "goalies.home"),
    ("decision not true", "decision-not-a-bool", "error", "goalies.home.0.decision"),
    ("decision on a side with one goalie", "decision-one-goalie", "warning", "goalies.home.0.decision"),
    ("score missing", "score-missing", "error", "score"),
    ("score missing, in a draft", "score-missing-draft", "warning", "score"),
    ("score not a block", "score-not-a-block", "error", "score"),
    ("score: an unknown side", "score-unknown-side", "error", "score.zzz"),
    ("score.<side> missing", "score-one-side", "error", "score.away"),
    ("score.<side> not a block", "score-side-not-a-block", "error", "score.home"),
    ("score.<side>: an unknown box", "score-unknown-key", "error", "score.home.shots"),
    ("periods missing", "periods-missing", "error", "score.home.periods"),
    ("periods not a list of rules.periods numbers", "periods-wrong-length", "error", "score.home.periods"),
    ("periods.<i> empty", "period-box-empty", "error", "score.home.periods.1"),
    ("periods.<i> empty, in a draft", "period-box-draft", "warning", "score.home.periods.1"),
    ("periods.<i> not a whole number", "period-box-text", "error", "score.home.periods.1"),
    ("periods.<i> not the side's goals in that period", "period-box-wrong", "error", "score.home.periods.1"),
    ("final missing", "final-missing", "error", "score.home.final"),
    ("final not a whole number", "final-not-a-number", "error", "score.home.final"),
    ("final not the periods plus OT plus SO", "final-wrong", "error", "score.home.final"),
    ("ot not a whole number", "ot-box-bad", "error", "score.home.ot"),
    ("ot filled although regulation was not level", "ot-not-level", "error", "score.home.ot"),
    ("ot filled although the league plays no overtime", "ot-when-none", "error", "score.home.ot"),
    ("an overtime goal line although there is no overtime", "ot-when-none", "error", "goals.4.period"),
    ("an overtime goal line although regulation was not level", "ot-goal-not-level", "error", "goals.8.period"),
    ("ot filled although regulation was not level (playoffs)", "playoff-ot-not-level", "error", "score.home.ot"),
    ("ot empty although regulation was level", "ot-missing", "error", "score.home.ot"),
    ("ot empty although regulation was level, in a draft", "ot-missing-draft", "warning", "score.home.ot"),
    ("ot empty although regulation was level (playoffs)", "playoff-ot-missing", "error", "score.home.ot"),
    ("ot not the side's goals in overtime", "ot-box-wrong", "error", "score.home.ot"),
    ("more than one overtime goal", "two-ot-goals", "error", "goals.5.period"),
    ("so filled although there is no shootout in this game", "so-without-shootout", "error", "score.home.so"),
    ("shootout filled although this league plays none", "so-and-shootout-when-none", "error", "shootout"),
    ("shootout filled although overtime was won", "shootout-not-needed", "error", "shootout"),
    ("shootout filled although the game was won in regulation", "shootout-not-level", "error", "shootout"),
    ("shootout and so filled although a level overtime is a tie here", "shootout-after-ot-tie", "error", "score.home.so"),
    ("shootout filled although a playoff league plays sudden death", "playoff-no-shootout-by-default", "error", "shootout"),
    ("shootout missing although level after overtime", "shootout-missing", "error", "shootout"),
    ("so missing although a shootout was played", "so-box-missing", "error", "score.home.so"),
    ("shootout not a block", "shootout-not-a-block", "error", "shootout"),
    ("shootout: an unknown key", "shootout-unknown-key", "error", "shootout.judge"),
    ("shootout.first missing", "shootout-first-missing", "error", "shootout.first"),
    ("shootout.first not home or away", "shootout-first-bad", "error", "shootout.first"),
    ("shootout.<side> missing", "shootout-side-missing", "error", "shootout.away"),
    ("shootout.<side> not a list", "shootout-side-not-a-list", "error", "shootout.away"),
    ("an attempt not a row", "shootout-attempt-not-a-block", "error", "shootout.home.0"),
    ("an attempt with an unknown key", "shootout-attempt-unknown-key", "error", "shootout.home.0.move"),
    ("an attempt's num not on the roster", "shootout-not-on-roster", "error", "shootout.home.0.num"),
    ("an attempt's scored not true or false", "shootout-scored-bad", "error", "shootout.home.0.scored"),
    ("an attempt's scored missing", "shootout-scored-missing", "error", "shootout.home.0.scored"),
    ("a shootout level at the end", "shootout-level", "error", "shootout"),
    ("a round missing", "shootout-round-missing", "warning", "shootout"),
    ("shots after the shootout was decided", "shootout-after-decided", "warning", "shootout"),
    ("so not 1 for the winner", "so-box-wrong-winner", "error", "score.home.so"),
    ("so not 0 or 1", "so-box-not-0-1", "error", "score.home.so"),
]


@pytest.mark.parametrize("what, name, level, at", ROWS, ids=[f"{i}-{r[0]}" for i, r in enumerate(ROWS)])
def test_every_row_of_the_checks_table_has_a_fixture(what, name, level, at):
    assert name in CASES, f"no fixture {name}.yml for: {what}"
    problems, _ = run(name)
    assert (level, at) in [(p["level"], p["at"]) for p in problems], (what, problems)


# ------------------------------------------------------------------ the cases that should be quiet, and the numbers they give

QUIET = ("clean", "tie", "ot-win", "ot-win-shootout-league", "ot-scoreless-tie", "shootout-win", "shootout-only",
         "shootout-early-stop", "shootout-sudden-death", "playoff-sudden-death-ot2", "playoff-shootout",
         "playoff-scoreless-ot", "gwg-in-ot", "gwg-out-of-order-lines", "goal-order-between-periods", "clock-remaining",
         "pp-goal", "sh-goal", "en-goal", "ps-goal", "bench-penalty", "bench-penalty-unserved", "major-and-misconduct",
         "two-goalies-decision", "backup-goalie-dressed", "goalie-skates", "shots-recorded", "shutout", "shared-shutout", "no-shutout-empty-net", "goalie-assist",
         "roster-00", "periods-2", "goals-left-out", "penalties-left-out")
WARNING_ONLY = ("pp-without-penalty", "sh-without-penalty", "time-out-of-order", "time-out-of-order-remaining",
                "penalty-time-out-of-order", "odd-minutes", "goal-cap", "decision-one-goalie", "spare-other-team",
                "draft-with-name", "shootout-round-missing", "shootout-after-decided")


@pytest.mark.parametrize("name", QUIET)
def test_these_cases_have_no_problem_at_all(name):
    problems, reading = run(name)
    assert problems == []
    assert reading is not None


@pytest.mark.parametrize("name", WARNING_ONLY)
def test_these_cases_have_warnings_and_still_read(name):
    problems, reading = run(name)
    assert problems and all(p["level"] == "warning" for p in problems)
    assert reading is not None


def lines_of(reading, group):
    return {ln["player"]: ln["counts"] for ln in reading["lines"] if ln["group"] == group}


def test_the_clean_game_is_the_mockup_game():
    _, reading = run("clean")
    score, facts = reading["score"], reading["facts"]
    assert score["final"] == {"home": 5, "away": 3}
    assert score["periods"] == {"home": [2, 1, 2], "away": [1, 2, 0]}
    assert score["extra"] == {} and score["decided_in"] == "regulation"
    assert score["final_at"] == {"home": "sheet.score.home.final", "away": "sheet.score.away.final"}
    assert [g["score"] for g in facts["goals"]] == [[1, 0], [1, 1], [2, 1], [2, 2], [3, 2], [3, 3], [4, 3], [5, 3]]
    assert [g["gwg"] for g in facts["goals"]] == [False] * 6 + [True, False]
    assert facts["pim"] == {"home": 4, "away": 4}
    assert reading["team_lines"] == {}


def test_a_player_gets_a_skater_line_and_a_goalie_gets_a_goalie_line():
    _, reading = run("clean")
    skaters, goalies = lines_of(reading, "skater"), lines_of(reading, "goalie")
    assert set(goalies) == {"len-t", "murray-b"} and "len-t" not in skaters
    assert len(skaters) == 10
    assert skaters["gord-p"] == {"g": 2, "a": 2, "pts": 4, "pim": 0, "ppg": 0, "shg": 0, "gwg": 1}
    assert skaters["barry-s"]["pts"] == 3 and skaters["doug-h"]["pim"] == 2
    assert goalies["len-t"] == {"w": 1, "l": 0, "t": 0, "otl": 0, "ga": 3, "sa": 0, "sho": 0, "a": 0, "pim": 0}
    assert goalies["murray-b"]["l"] == 1 and goalies["murray-b"]["ga"] == 5


def test_the_game_winner_follows_the_clock_not_the_order_of_the_lines():
    _, reading = run("gwg-out-of-order-lines")
    assert [(g["period"], g["time"]) for g in reading["facts"]["goals"]][:3] == [(1, "4:12"), (1, "9:38"), (1, "13:05")]
    assert [g["time"] for g in reading["facts"]["goals"] if g["gwg"]] == ["5:31"]
    assert [g["score"] for g in reading["facts"]["goals"]] == [g["score"] for g in run("clean")[1]["facts"]["goals"]]


def test_the_remaining_clock_puts_the_goals_in_the_same_order():
    _, reading = run("clock-remaining")
    _, clean = run("clean")
    assert [g["score"] for g in reading["facts"]["goals"]] == [g["score"] for g in clean["facts"]["goals"]]
    assert [g["gwg"] for g in reading["facts"]["goals"]] == [g["gwg"] for g in clean["facts"]["goals"]]


def test_a_tie_has_no_winning_goal_and_both_goalies_get_a_tie():
    _, reading = run("tie")
    assert not any(g["gwg"] for g in reading["facts"]["goals"])
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["t"] == 1 and goalies["murray-b"]["t"] == 1
    assert goalies["len-t"]["w"] == goalies["len-t"]["l"] == 0


def test_an_overtime_win_is_decided_in_overtime_and_the_overtime_goal_is_the_winner():
    _, reading = run("ot-win")
    score = reading["score"]
    assert score["decided_in"] == "overtime" and score["extra"] == {"home": [1], "away": [0]}
    assert score["final"] == {"home": 3, "away": 2}
    assert [g["period"] for g in reading["facts"]["goals"] if g["gwg"]] == ["OT"]
    goalies = lines_of(reading, "goalie")
    assert goalies["murray-b"]["l"] == 1 and goalies["murray-b"]["otl"] == 1 and goalies["len-t"]["w"] == 1


def test_the_sudden_death_overtime_period_is_kept_as_written():
    _, reading = run("playoff-sudden-death-ot2")
    assert [g["period"] for g in reading["facts"]["goals"]][-1] == "OT2"
    assert reading["score"]["extra"] == {"home": [1], "away": [0]}


def test_a_shootout_adds_one_goal_to_the_winner_and_gives_nobody_a_goal_or_a_goal_against():
    _, reading = run("shootout-win")
    score, facts = reading["score"], reading["facts"]
    assert score["final"] == {"home": 3, "away": 2} and score["decided_in"] == "shootout"
    assert score["extra"] == {"home": [0, 1], "away": [0, 0]} and score["periods"] == {"home": [1, 0, 1], "away": [0, 1, 1]}
    assert not any(g["gwg"] for g in facts["goals"])
    assert facts["shootout"]["tally"] == {"home": 2, "away": 1} and facts["shootout"]["winner"] == "home"
    assert [a["side"] for a in facts["shootout"]["attempts"]] == ["home", "away"] * 3
    assert sum(ln["counts"]["g"] for ln in reading["lines"] if ln["group"] == "skater") == 4
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["ga"] == 2 and goalies["murray-b"]["ga"] == 2 and goalies["murray-b"]["otl"] == 1


def test_a_shootout_with_no_overtime_has_only_the_shootout_in_extra():
    _, reading = run("shootout-only")
    assert reading["score"]["extra"] == {"home": [1], "away": [0]}
    assert reading["facts"]["ot_played"] is False and reading["facts"]["so_played"] is True


def test_the_team_that_shot_second_orders_the_attempts_after_the_first():
    _, reading = run("shootout-sudden-death")
    attempts = reading["facts"]["shootout"]["attempts"]
    assert [a["side"] for a in attempts] == ["away", "home"] * 4
    assert reading["facts"]["shootout"]["winner"] == "away" and reading["score"]["final"] == {"home": 2, "away": 3}


def test_a_two_goalie_game_gives_the_decision_to_one_goalie_and_a_game_to_both():
    _, reading = run("two-goalies-decision")
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["ga"] == 2 and goalies["len-t"]["w"] == 0
    assert goalies["stu-g"]["ga"] == 1 and goalies["stu-g"]["w"] == 1
    assert [g["decision"] for g in reading["facts"]["goalies"]["home"]] == [False, True]


def test_a_goalie_who_played_the_whole_game_and_allowed_nothing_has_a_shutout():
    _, reading = run("shutout")
    assert lines_of(reading, "goalie")["len-t"]["sho"] == 1
    assert lines_of(reading, "goalie")["murray-b"]["sho"] == 0


def test_a_shared_shutout_is_credited_to_nobody():
    _, reading = run("shared-shutout")
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["sho"] == 0 and goalies["stu-g"]["sho"] == 0 and goalies["stu-g"]["w"] == 1


def test_an_empty_net_goal_is_not_a_goal_against_but_it_ends_the_shutout():
    _, reading = run("no-shutout-empty-net")
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["ga"] == 0 and goalies["len-t"]["sho"] == 0 and goalies["len-t"]["l"] == 1
    assert goalies["murray-b"]["sho"] == 1
    _, reading = run("en-goal")
    assert lines_of(reading, "goalie")["murray-b"]["ga"] == 5 and reading["score"]["final"]["home"] == 6


def test_a_goalie_with_an_assist_and_a_penalty_keeps_them_on_his_goalie_line():
    _, reading = run("goalie-assist")
    line = lines_of(reading, "goalie")["len-t"]
    assert line["a"] == 1 and line["pim"] == 2
    assert "len-t" not in lines_of(reading, "skater")


def test_a_bench_penalty_counts_to_the_team_and_to_nobody_else():
    _, reading = run("bench-penalty")
    assert reading["facts"]["pim"] == {"home": 6, "away": 4}
    assert sum(c["pim"] for c in lines_of(reading, "skater").values()) == 8
    penalty = next(p for p in reading["facts"]["penalties"] if p["bench"])
    assert penalty["num"] == "bench" and penalty["player"] is None and penalty["served_by"]["player"] == "terry-w"


def test_power_play_and_short_handed_goals_are_counted_for_the_scorer():
    _, reading = run("pp-goal")
    assert lines_of(reading, "skater")["ken-l"]["ppg"] == 1
    _, reading = run("sh-goal")
    assert lines_of(reading, "skater")["doug-h"]["shg"] == 1


def test_shots_are_counted_when_recorded():
    _, reading = run("shots-recorded")
    goalies = lines_of(reading, "goalie")
    assert goalies["len-t"]["sa"] == 28 and goalies["murray-b"]["sa"] == 30


def test_jersey_00_is_a_number_and_looks_the_player_up():
    _, reading = run("roster-00")
    assert lines_of(reading, "skater")["terry-w"]["a"] == 1
    assert reading["facts"]["goals"][-1]["assists"][1] == {"num": "00", "player": "terry-w", "name": None}


def test_a_spare_written_in_by_name_gets_no_line():
    _, reading = run("draft-with-name")
    assert "terry-w" not in lines_of(reading, "skater")
    assert len([ln for ln in reading["lines"] if ln["group"] == "skater"]) == 9


def test_a_backup_goalie_who_dressed_and_did_not_play_gets_no_game_at_all():
    _, reading = run("backup-goalie-dressed")
    assert "stu-g" not in lines_of(reading, "skater") and "stu-g" not in lines_of(reading, "goalie")
    assert len(lines_of(reading, "skater")) == 10 and set(lines_of(reading, "goalie")) == {"len-t", "murray-b"}


def test_a_goalie_who_skated_gets_a_skater_line():
    _, reading = run("goalie-skates")
    skaters = lines_of(reading, "skater")
    assert skaters["stu-g"] == {"g": 0, "a": 0, "pts": 0, "pim": 2, "ppg": 0, "shg": 0, "gwg": 0}
    assert "stu-g" not in lines_of(reading, "goalie") and len(skaters) == 11


def test_a_two_period_league_has_two_period_boxes():
    _, reading = run("periods-2")
    assert len(reading["score"]["periods"]["home"]) == 2 and reading["facts"]["periods"] == 2


# ------------------------------------------------------------------ properties of check over every fixture

def get(node, parts):
    for part in parts:
        if isinstance(node, dict):
            node = next(v for k, v in node.items() if str(k) == part)
        else:
            node = node[int(part)]
    return node


def resolves(sheet, at):
    """The path leads to a node, or to a missing key whose parent exists (a block or a list)."""
    if at == "":
        return True
    parts = at.split(".")
    for cut in (len(parts), len(parts) - 1):
        try:
            node = get(sheet, parts[:cut])
        except (StopIteration, KeyError, IndexError, ValueError, TypeError):
            continue
        return cut == len(parts) or isinstance(node, (dict, list))
    return False


@pytest.mark.parametrize("name", CASES)
def test_every_path_points_into_the_sheet_and_check_changes_nothing(name):
    case = load_case(name)
    ctx = context_for(case)
    sheet, ctx_before = copy.deepcopy(case["sheet"]), copy.deepcopy(ctx)
    for p in SPORT.rules.check(sheet, ctx):
        assert resolves(sheet, p.at), (p.at, p.message)
        assert p.message and p.message == p.message.strip()
    assert sheet == case["sheet"] and ctx == ctx_before


@pytest.mark.parametrize("name", CASES)
def test_a_draft_is_never_stricter_than_a_final_file(name):
    case = load_case(name)
    ctx = context_for(case)
    final = SPORT.rules.check(case["sheet"], replace(ctx, folder="games"))
    draft = SPORT.rules.check(case["sheet"], replace(ctx, folder="drafts"))
    assert sum(p.level == "error" for p in draft) <= sum(p.level == "error" for p in final)
    assert [p.at for p in draft] == [p.at for p in final]
