"""The standings engine (scripts/core/standings.py, spec 3.5): every rule with a tiny hand-computed table.

Games are built with `g()`: periods are per-period scores; the final is their sum unless given. Teams are
a..f with names Aces, Bears, Cats, Dogs, Eels, Foxes (so "listed by name" is also alphabetical by id).
"""
import random
from fractions import Fraction

import pytest

from scripts.core.config import normalise_standings
from scripts.core.model import Problem, Reading, Score, Team
from scripts.core.standings import (
    TIEBREAKERS, StandingsGame, Table, TeamGame, compute_standings, game_results, normalise_tiebreakers, record_of,
    results_by_team, tiebreak_note, validate_tiebreakers,
)

NAMES = {"a": "Aces", "b": "Bears", "c": "Cats", "d": "Dogs", "e": "Eels", "f": "Foxes"}
TEAMS = {t: Team(t, n, t.upper() * 3) for t, n in NAMES.items()}
ALL_COLUMNS = ["gp", "w", "l", "t", "otw", "otl", "pts", "pct", "pf", "pa", "diff", "gb", "pw"]
FILE = "data/test/games/x.yml"


def S(**over):
    """A standings setting: 2-1-0, no period points, no tiebreakers, every column; `over` changes keys.
    `points` is merged key by key like the config does."""
    base = {"points": {"win": 2, "tie": 1, "loss": 0}, "columns": ["gp", "w", "l", "t", "pts", "pf", "pa", "diff"]}
    points = {**base["points"], **over.pop("points", {})}
    return normalise_standings({**base, **over, "points": points})


def g(gid, home, away, hp, ap, final=None, extra=None, decided_in="regulation", type="regular"):
    """A finished game; hp/ap are the home/away period scores (a number means one period)."""
    hp, ap = ([hp] if isinstance(hp, int) else hp), ([ap] if isinstance(ap, int) else ap)
    extra = extra or {}
    total = final or {"home": sum(hp) + sum(extra.get("home", [])), "away": sum(ap) + sum(extra.get("away", []))}
    score = Score(final=total, periods={"home": list(hp), "away": list(ap)}, extra=extra, decided_in=decided_in,
                  final_at={"home": "sheet.final.home", "away": "sheet.final.away"})
    return StandingsGame(gid, home, away, Reading(score), type=type, file=f"data/test/games/{gid}.yml")


def forfeit(gid, home, away, by, type="regular"):
    return StandingsGame(gid, home, away, None, type=type, forfeit=by, file=f"data/test/games/{gid}.yml")


def table(games, standings=None, periods=1, teams=None, **kw):
    return compute_standings(games, {t: TEAMS[t] for t in "abcd"} if teams is None else teams, standings or S(),
                             regulation_periods=periods, **kw)


def order(result):
    return [(r["team"], r["rank"]) for r in result.rows]


def col(result, name, shown=True):
    return {r["team"]: r["display" if shown else "values"][name] for r in result.rows}


# ------------------------------------------------------------------ points rules

def test_points_two_one_nothing():
    res = table([g("g1", "a", "b", 10, 8), g("g2", "c", "d", 7, 7)])
    assert col(res, "pts") == {"a": "2", "c": "1", "d": "1", "b": "0"}
    assert order(res) == [("a", 1), ("c", 2), ("d", 2), ("b", 4)]      # c and d level: shared rank 2, by name


def test_points_three_one_nothing():
    res = table([g("g1", "a", "b", 10, 8), g("g2", "c", "d", 7, 7)], S(points={"win": 3}))
    assert col(res, "pts") == {"a": "3", "c": "1", "d": "1", "b": "0"}


def test_masters_period_rule_one_point_per_period_won():
    # Q1 6-5 aces, Q2 5-6 bears, Q3 4-4 (nobody), Q4 5-3 aces; aces win 20-18: 3 + 2 periods = 5; bears 1 period
    game = g("g1", "a", "b", [6, 5, 4, 5], [5, 6, 4, 3])
    res = table([game], S(points={"win": 3, "tie": 0, "loss": 0}, period_points=1), periods=4)
    assert col(res, "pts") == {"a": "5", "b": "1", "c": "0", "d": "0"}
    results, _ = game_results(game, S(points={"win": 3, "tie": 0, "loss": 0}, period_points=1), 4)
    assert (results["a"].points, results["a"].periods_won, results["b"].points, results["b"].periods_won) == (5, 2, 1, 1)


def test_overtime_win_and_loss_use_their_own_points():
    ot = g("g1", "a", "b", 5, 5, extra={"home": [7], "away": [5]}, decided_in="overtime")
    res = table([ot], S(points={"ot_loss": 1}, columns=["gp", "w", "l", "otw", "otl", "pts", "pf", "pa"]))
    assert col(res, "pts") == {"a": "2", "b": "1", "c": "0", "d": "0"}
    assert col(res, "otw")["a"] == "1" and col(res, "otl")["b"] == "1"
    assert col(res, "w")["a"] == "1" and col(res, "l")["b"] == "1"       # w and l include the overtime ones
    assert (col(res, "pf")["a"], col(res, "pa")["a"]) == ("12", "10")


def test_ot_points_default_to_win_and_loss():
    ot = g("g1", "a", "b", 5, 5, extra={"home": [7], "away": [5]}, decided_in="overtime")
    assert col(table([ot]), "pts") == {"a": "2", "b": "0", "c": "0", "d": "0"}


def test_a_tied_period_gives_nobody_a_point_and_unplayed_periods_are_skipped():
    game = g("g1", "a", "b", [4, None], [4, None], final={"home": 8, "away": 7})
    results, problems = game_results(game, S(period_points=1), 2)
    assert problems == [] and (results["a"].periods_won, results["b"].periods_won) == (0, 0)


# ------------------------------------------------------------------ forfeits

def test_fixed_forfeit_uses_the_score_and_earns_no_period_points():
    st = S(period_points=1, forfeit={"score": [7, 0]}, columns=["gp", "w", "l", "pts", "pf", "pa", "pw"])
    res = table([forfeit("g1", "a", "b", by="b")], st, periods=4)
    assert col(res, "pts")["a"] == "2" and col(res, "pts")["b"] == "0"
    assert (col(res, "pf")["a"], col(res, "pa")["a"], col(res, "pf")["b"], col(res, "pa")["b"]) == ("7", "0", "0", "7")
    assert col(res, "gp")["a"] == "1" and col(res, "w")["a"] == "1" and col(res, "l")["b"] == "1"
    assert col(res, "pw")["a"] == "0"


def test_per_period_forfeit_is_one_nil_in_every_regulation_period():
    st = S(points={"win": 3, "tie": 0}, period_points=1, forfeit={"score": "per_period"}, columns=["pts", "pf", "pa", "pw"])
    res = table([forfeit("g1", "a", "b", by="a")], st, periods=4)      # a forfeits, b wins
    assert col(res, "pts")["b"] == "7" and col(res, "pts")["a"] == "0"          # 3 + 4 periods
    assert (col(res, "pf")["b"], col(res, "pa")["b"], col(res, "pw")["b"], col(res, "pw")["a"]) == ("4", "0", "4", "0")


def test_forfeit_by_a_stranger_is_a_problem():
    _, problems = game_results(forfeit("g1", "a", "b", by="c"), S(), 1)
    assert [(p.level, p.at, p.file) for p in problems] == [("error", "forfeit", "data/test/games/g1.yml")]


def test_forfeit_games_show_in_results_by_team():
    by_team, _ = results_by_team([forfeit("g1", "a", "b", by="b")], "ab", S(), 2)
    assert by_team["a"][0].forfeit and by_team["a"][0].result == "win" and by_team["b"][0].result == "loss"


# ------------------------------------------------------------------ ties and playoffs

def test_tie_when_ties_are_allowed_is_a_tie():
    res = table([g("g1", "a", "b", 5, 5)], S(columns=["w", "l", "t", "pts"]))
    assert col(res, "t") == {"a": "1", "b": "1", "c": "0", "d": "0"} and col(res, "pts")["a"] == "1"
    assert res.problems == []


def test_tie_when_ties_are_not_allowed_is_an_error_at_the_final_box():
    res = table([g("g1", "a", "b", 5, 5)], S(ties=False))
    assert res.problems == [Problem("error", "sheet.final.home", res.problems[0].message, "data/test/games/g1.yml")]
    assert "tied" in res.problems[0].message
    assert col(res, "gp")["a"] == "0"                                         # the game is left out


def test_tied_playoff_game_is_always_an_error():
    res = table([g("p1", "a", "b", 5, 5, type="playoff")], S(ties=True))
    assert [(p.level, p.at, p.file) for p in res.problems] == [("error", "sheet.final.home", "data/test/games/p1.yml")]
    assert "playoff" in res.problems[0].message


def test_playoff_games_never_count():
    res = table([g("g1", "a", "b", 9, 3), g("p1", "b", "a", 40, 1, type="playoff"), forfeit("p2", "a", "b", "a", "playoff")])
    assert col(res, "gp") == {"a": "1", "b": "1", "c": "0", "d": "0"} and col(res, "pts")["a"] == "2"
    assert res.problems == []


def test_a_team_outside_the_season_is_a_problem():
    res = table([g("g1", "a", "z", 3, 1)])
    assert [p.at for p in res.problems] == ["away"] and col(res, "gp")["a"] == "0"


def test_a_game_with_nothing_is_a_problem():
    res = table([StandingsGame("g1", "a", "b", None, file="f.yml")])
    assert [(p.at, p.file) for p in res.problems] == [("", "f.yml")]


# ------------------------------------------------------------------ the tiebreakers

def test_head_to_head_wins_over_goal_difference():
    # d: 4 points. a and b both 2: b beat a 10-9, but a is +29 on the season and b is 0.
    games = [g("g1", "a", "b", 9, 10), g("g2", "a", "c", 30, 0), g("g3", "d", "b", 10, 9), g("g4", "d", "c", 5, 4)]
    res = table(games, S(tiebreakers=["head_to_head", "diff"]))
    assert order(res) == [("d", 1), ("b", 2), ("a", 3), ("c", 4)]
    assert {r["team"]: r["broke_by"] for r in res.rows} == {"d": None, "b": "head_to_head", "a": "head_to_head", "c": None}
    assert not any(r["tied"] for r in res.rows)


def test_head_to_head_is_skipped_when_the_tied_teams_have_not_all_met():
    # a (+10) and b (+5) are level on 2 points and never met; c (-10) and d (-5) level on 0
    games = [g("g1", "a", "c", 20, 10), g("g2", "b", "d", 15, 10)]
    res = table(games, S(tiebreakers=["head_to_head", "wins", "diff"]))
    assert order(res) == [("a", 1), ("b", 2), ("d", 3), ("c", 4)]
    assert {r["team"]: r["broke_by"] for r in res.rows} == {"a": "diff", "b": "diff", "d": "diff", "c": "diff"}


def test_head_to_head_needs_every_pair_not_just_one_each():
    # a, b, c level on 2 points; a-b and b-c have met but a-c have not: skipped, so wins (all 1) then pf decide
    games = [g("g1", "a", "b", 5, 1), g("g2", "c", "b", 6, 1), g("g3", "d", "a", 2, 1), g("g4", "d", "c", 2, 1)]
    st = S(points={"win": 2}, tiebreakers=["head_to_head", "points_for"])
    res = table(games, st)
    # a: W,L = 2 pts, pf 6; b: L,L = 0; c: W,L = 2, pf 8; d: W,W = 4. a-c never met.
    assert order(res) == [("d", 1), ("c", 2), ("a", 3), ("b", 4)]
    assert {r["team"]: r["broke_by"] for r in res.rows}["c"] == "points_for"


def test_wins_separates_teams_level_on_points_and_the_rest_share_a_rank():
    # 3-1-0: a won once (3 points), b tied three times (3 points); c, d, e have a tie each (1 point)
    games = [g("g1", "a", "e", 5, 0), g("g2", "b", "c", 3, 3), g("g3", "b", "d", 2, 2), g("g4", "b", "e", 1, 1)]
    teams = {t: TEAMS[t] for t in "abcde"}
    res = table(games, S(points={"win": 3}, tiebreakers=["head_to_head", "wins"]), teams=teams)
    assert order(res) == [("a", 1), ("b", 2), ("c", 3), ("d", 3), ("e", 3)]      # c, d, e share 3rd, by name
    rows = {r["team"]: r for r in res.rows}
    assert (rows["a"]["broke_by"], rows["b"]["broke_by"], rows["c"]["broke_by"]) == ("wins", "wins", None)
    assert rows["c"]["tied"] and rows["e"]["tied"] and not rows["a"]["tied"]


def test_win_pct_breaker_with_unequal_games():
    # 2-1-0: a one win (2 points, 1.000); b two ties (2 points, .500); d and e one tie each (1 point, .500)
    games = [g("g1", "a", "c", 3, 0), g("g2", "b", "d", 1, 1), g("g3", "b", "e", 2, 2)]
    teams = {t: TEAMS[t] for t in "abcde"}
    res = table(games, S(tiebreakers=["win_pct"]), teams=teams)
    assert order(res) == [("a", 1), ("b", 2), ("d", 3), ("e", 3), ("c", 5)]
    assert {r["team"]: r["broke_by"] for r in res.rows}["a"] == "win_pct"


GAMES_DIFF = [g("g1", "a", "c", 50, 0), g("g2", "d", "a", 40, 10), g("g3", "b", "e", 12, 5), g("g4", "f", "b", 6, 5)]


def test_diff_and_capped_diff():
    # level on 2 points: a (+50 -30 = +20), b (+7 -1 = +6), d (+30), f (+1); e -7 and c -50 are level on 0
    teams = {t: TEAMS[t] for t in "abcdef"}
    plain = table(GAMES_DIFF, S(tiebreakers=["diff"]), teams=teams)
    assert [t for t, _ in order(plain)] == ["d", "a", "b", "f", "e", "c"]
    # each game's margin counted at most 7: a 7-7 = 0, b 7-1 = 6, d +7, f +1; e -7, c -7 (level, shared rank)
    capped = table(GAMES_DIFF, S(tiebreakers=[{"diff": {"cap": 7}}]), teams=teams)
    assert order(capped) == [("d", 1), ("b", 2), ("f", 3), ("a", 4), ("c", 5), ("e", 5)]


def two_team_edge(**periods):
    """x beats c 10-0 in two periods (won both); y beats d 20-18 (won one, tied one): level on 2 points."""
    return [g("g1", "a", "c", [5, 5], [0, 0]), g("g2", "b", "d", [10, 10], [10, 8])]


@pytest.mark.parametrize("breaker, first", [("points_for", "b"), ("points_against", "a"), ("diff", "a"),
                                            ("periods_won", "a")])
def test_single_value_breakers(breaker, first):
    # a: pf 10, pa 0, diff +10, won 2 periods; b: pf 20, pa 18, diff +2, won 1 period (one tied)
    res = table(two_team_edge(), S(tiebreakers=[breaker]), periods=2)
    assert [t for t, _ in order(res)][:2] == [first, "b" if first == "a" else "a"]
    assert {r["team"]: r["broke_by"] for r in res.rows}[first] == breaker


def test_breaker_functions_on_a_hand_built_table():
    def tg(team, opp, result, points, pf=1, pa=0):
        return TeamGame("x", team, opp, "home", result, points, pf, pa, 0)

    games = {"a": (tg("a", "b", "win", 5), tg("a", "c", "loss", 0), tg("a", "d", "win", 3)),
             "b": (tg("b", "a", "loss", 1), tg("b", "c", "win", 4)),
             "c": (tg("c", "a", "win", 5), tg("c", "b", "loss", 0)),
             "d": (tg("d", "a", "loss", 0),)}
    t = Table({k: record_of(v) for k, v in games.items()}, games)
    # among a, b, c: a 5 and 0 points in two games, b 1 and 4, c 5 and 0
    assert TIEBREAKERS["head_to_head_points"](t, ["a", "b", "c"]) == {"a": 2.5, "b": 2.5, "c": 2.5}
    assert TIEBREAKERS["head_to_head_points"](t, ["a", "b"]) == {"a": 5, "b": 1}
    assert TIEBREAKERS["head_to_head"](t, ["a", "b"]) == {"a": 1, "b": 0}
    assert TIEBREAKERS["head_to_head_points"](t, ["b", "d"]) is None                 # b and d never met
    assert TIEBREAKERS["head_to_head"](t, ["b", "d"]) is None
    assert TIEBREAKERS["head_to_head"](t, ["a", "b", "d"]) is None                   # b and d again
    assert TIEBREAKERS["wins"](t, ["a", "b"]) == {"a": 2, "b": 1}
    assert TIEBREAKERS["win_pct"](t, ["a", "d"]) == {"a": Fraction(2, 3), "d": 0}


def test_cycles_stay_level():
    # a beat b, b beat c, c beat a: everyone 3 points and 1.5 per game against the others: shared rank 1
    games = [g("g1", "a", "b", 1, 0), g("g2", "b", "c", 1, 0), g("g3", "c", "a", 1, 0)]
    teams = {t: TEAMS[t] for t in "abc"}
    res = table(games, S(points={"win": 3}, tiebreakers=["head_to_head", "head_to_head_points"]), teams=teams)
    assert order(res) == [("a", 1), ("b", 1), ("c", 1)] and all(r["tied"] and r["broke_by"] is None for r in res.rows)


def test_head_to_head_points_separates_teams_head_to_head_cannot():
    # 3-1-0 plus a point per period won, two periods. a and b both end on 6.
    # g1: a wins both periods: a 5, b 0. g2: b wins the game 4-3 but a takes the second period: b 4, a 1.
    # g3: b and d tie 2-2, a period each: 1 + 1 for b (and d). Head-to-head is 1-1; per game a has 3, b 2.
    st = S(points={"win": 3, "tie": 1, "loss": 0}, period_points=1, tiebreakers=["head_to_head", "head_to_head_points"])
    games = [g("g1", "a", "b", [2, 2], [1, 1]), g("g2", "b", "a", [3, 1], [1, 2]), g("g3", "b", "d", [2, 0], [1, 1])]
    res = table(games, st, periods=2)
    assert col(res, "pts") == {"a": "6", "b": "6", "d": "2", "c": "0"}
    assert order(res) == [("a", 1), ("b", 2), ("d", 3), ("c", 4)]
    assert res.rows[0]["broke_by"] == "head_to_head_points" and res.rows[0]["tiebreak"] == "head-to-head points"


def test_three_way_tie_runs_the_breakers_in_order_without_restarting():
    # a, b, c are level on 6 points. Among the three: a 3-1 (.75), b 1-2, c 1-2 (.333): head_to_head puts a
    # first and leaves b and c level. Restarting head_to_head on b and c alone would put b first (b beat c);
    # moving on to diff puts c first (+59 against +19).
    games = [g("g1", "a", "b", 10, 9), g("g2", "a", "b", 10, 9), g("g3", "a", "c", 10, 9), g("g4", "c", "a", 10, 9),
             g("g5", "b", "c", 10, 9), g("g6", "b", "d", 10, 0), g("g7", "b", "d", 10, 0),
             g("g8", "c", "e", 30, 0), g("g9", "c", "e", 30, 0)]
    teams = {t: TEAMS[t] for t in "abcde"}
    st = S(points={"win": 2}, tiebreakers=["head_to_head", "diff"])
    res = table(games, st, teams=teams)
    assert col(res, "pts") == {"a": "6", "b": "6", "c": "6", "d": "0", "e": "0"}
    assert order(res) == [("a", 1), ("c", 2), ("b", 3), ("d", 4), ("e", 5)]
    assert {r["team"]: r["broke_by"] for r in res.rows} == {"a": "head_to_head", "c": "diff", "b": "diff",
                                                           "d": "diff", "e": "diff"}


def test_teams_still_level_after_the_last_breaker_share_a_rank_listed_by_name():
    res = table([g("g1", "a", "b", 3, 1), g("g2", "c", "d", 3, 1)], S(tiebreakers=["wins"]))
    assert order(res) == [("a", 1), ("c", 1), ("b", 3), ("d", 3)]
    assert [r["tied"] for r in res.rows] == [True, True, True, True]


def test_no_tiebreakers_means_shared_ranks():
    res = table([g("g1", "a", "b", 3, 1)], S())
    assert order(res) == [("a", 1), ("b", 2), ("c", 2), ("d", 2)]            # all on 0 points: one shared rank
    res = table([g("g1", "a", "b", 3, 1), g("g2", "c", "d", 2, 2)], S())
    assert order(res) == [("a", 1), ("c", 2), ("d", 2), ("b", 4)]            # competition ranks: 1, 2, 2, 4


# ------------------------------------------------------------------ rank_by

def test_rank_by_win_pct_with_unequal_games():
    # x=a plays 1 game and wins; y=b plays 3 and wins 2; s=c plays 1 and wins. Points rank b first (4 points).
    games = [g("g1", "a", "d", 3, 0), g("g2", "b", "e", 3, 0), g("g3", "b", "f", 3, 0), g("g4", "c", "b", 3, 0)]
    teams = {t: TEAMS[t] for t in "abcdef"}
    by_points = table(games, S(rank_by="points"), teams=teams)
    assert [t for t, _ in order(by_points)][0] == "b"
    by_pct = table(games, S(rank_by="win_pct"), teams=teams)
    assert order(by_pct) == [("a", 1), ("c", 1), ("b", 3), ("d", 4), ("e", 4), ("f", 4)]
    assert col(by_pct, "pts")["b"] == "4"


# ------------------------------------------------------------------ formatting

def test_pct_diff_and_gb_formatting():
    games = [g("g1", "a", "b", 10, 4), g("g2", "a", "c", 8, 3), g("g3", "a", "d", 6, 6), g("g4", "b", "c", 5, 5)]
    res = table(games, S(columns=ALL_COLUMNS))
    rows = {r["team"]: r for r in res.rows}
    assert rows["a"]["display"]["pct"] == ".833" and rows["a"]["values"]["pct"] == 0.833
    assert rows["a"]["record"] == "2-0-1" and rows["b"]["record"] == "0-1-1"
    assert rows["b"]["display"]["pct"] == ".250" and rows["d"]["display"]["pct"] == ".500"
    assert [rows[t]["display"]["diff"] for t in "abcd"] == ["+11", "−6", "−5", "0"]       # real minus sign
    assert [rows[t]["display"]["gb"] for t in "abcd"] == ["—", "1.5", "1.5", "1"]
    assert rows["a"]["values"]["gb"] == 0 and rows["b"]["values"]["gb"] == 1.5 and rows["d"]["values"]["gb"] == 1
    assert rows["a"]["display"]["pts"] == "5" and rows["a"]["values"]["pts"] == 5


def test_unbeaten_pct_and_empty_season():
    res = table([g("g1", "a", "b", 2, 1)], S(columns=["pct", "gb"]))
    assert col(res, "pct") == {"a": "1.000", "c": ".000", "d": ".000", "b": ".000"}
    empty = table([], S(columns=["gp", "pct", "gb"]))
    assert [r["rank"] for r in empty.rows] == [1, 1, 1, 1] and col(empty, "gb") == {t: "—" for t in "abcd"}
    assert table([], S(), teams={}).rows == []


def test_team_stat_columns_are_summed_from_team_lines():
    def with_stats(game, home, away):
        game.reading.team_lines.update({"home": home, "away": away})
        return game

    games = [with_stats(g("g1", "a", "b", 3, 1), {"ends": 4}, {"ends": 2}),
             with_stats(g("g2", "b", "a", 3, 1), {"ends": 5}, {})]
    res = table(games, S(columns=["gp", "ends"]))
    assert col(res, "ends") == {"a": "4", "b": "7", "c": "0", "d": "0"}


# ------------------------------------------------------------------ the note

def test_tiebreak_note_set():
    assert tiebreak_note(S(tiebreakers=["head_to_head", "wins"])) == \
        ("Teams level on points are ranked by head-to-head record (when they have all played each other), "
         "then wins; teams still level share a rank.")
    assert tiebreak_note(S(tiebreakers=[{"diff": {"cap": 7}}, "points_against"])) == \
        ("Teams level on points are ranked by score difference (each game counted up to 7), then fewest points "
         "against; teams still level share a rank.")
    # the skip rule is said once, at the first head-to-head breaker; "level on" follows rank_by
    assert tiebreak_note(S(rank_by="win_pct", tiebreakers=["head_to_head", "head_to_head_points"])) == \
        ("Teams level on win percentage are ranked by head-to-head record (when they have all played each "
         "other), then points in head-to-head games; teams still level share a rank.")
    assert tiebreak_note(S()) == "Teams level on points share a rank."
    assert tiebreak_note(S(rank_by="win_pct")) == "Teams level on win percentage share a rank."


def test_tiebreak_note_placeholder():
    note = tiebreak_note(S(tiebreakers=["head_to_head", "diff"]), unset=True)
    assert note.startswith("[placeholder] ") and note.endswith("Teams level on points are ranked by head-to-head record (when they have all played each "
                                                    "other), then score difference; teams still level share a rank.")
    assert table([], S(tiebreakers=["wins"]), tiebreakers_unset=True).tiebreak_note.startswith("[placeholder]")
    assert not table([], S(tiebreakers=["wins"])).tiebreak_note.startswith("[placeholder]")


# ------------------------------------------------------------------ validation

def test_validate_tiebreakers():
    assert validate_tiebreakers(["head_to_head", {"diff": {"cap": 7}}, "wins"]) == []
    assert validate_tiebreakers([]) == []
    bad = validate_tiebreakers(["head_to_head", "luck", {"wins": {"cap": 2}}, {"diff": {"cap": 0}},
                                {"diff": {"top": 1}}, {"a": 1, "b": 2}, "wins"])
    assert [p.at for p in bad] == ["standings.tiebreakers.1", "standings.tiebreakers.2.wins",
                                   "standings.tiebreakers.3.diff.cap", "standings.tiebreakers.4.diff",
                                   "standings.tiebreakers.4.diff", "standings.tiebreakers.5",
                                   "standings.tiebreakers.6"]       # 4: 'diff' twice, and an unknown option
    assert all(p.level == "error" for p in bad) and "luck" in bad[0].message and "head_to_head" in bad[0].message
    assert validate_tiebreakers("wins", at="x")[0].at == "x"
    assert validate_tiebreakers(["wins"], at="seasons.0.overrides.standings.tiebreakers") == []
    assert validate_tiebreakers(["wins", "wins"])[0].at == "standings.tiebreakers.1"
    assert set(TIEBREAKERS) == {"head_to_head", "head_to_head_points", "wins", "win_pct", "diff", "points_for",
                                "points_against", "periods_won"}


def test_registry_matches_the_config_schema():
    from scripts.core.sports import TIEBREAKERS as SCHEMA_NAMES
    assert set(TIEBREAKERS) == set(SCHEMA_NAMES)


def test_normalise_tiebreakers():
    assert normalise_tiebreakers(["wins", {"diff": {"cap": 3}}]) == [("wins", {}), ("diff", {"cap": 3})]
    with pytest.raises(ValueError):
        normalise_tiebreakers(["luck"])


def test_regulation_periods_must_be_positive():
    with pytest.raises(ValueError):
        table([], S(), periods=0)


# ------------------------------------------------------------------ determinism

def test_same_input_twice_and_input_order_irrelevant():
    games = GAMES_DIFF + [g("g5", "e", "f", 4, 4), forfeit("g6", "c", "d", "c"), g("p1", "a", "b", 1, 2, type="playoff")]
    teams = {t: TEAMS[t] for t in "abcdef"}
    st = S(tiebreakers=["head_to_head", {"diff": {"cap": 7}}, "points_for"], columns=ALL_COLUMNS)
    first = table(games, st, teams=teams)
    assert table(games, st, teams=teams).rows == first.rows
    shuffled = list(games)
    random.Random(7).shuffle(shuffled)
    reversed_teams = {t: teams[t] for t in reversed(list(teams))}
    again = table(shuffled, st, teams=reversed_teams)
    assert again.rows == first.rows and again.tiebreak_note == first.tiebreak_note
    assert {t: [x.game_id for x in v] for t, v in again.results.items()} == \
        {t: [x.game_id for x in v] for t, v in first.results.items()}


def test_inputs_are_not_changed():
    st = S(tiebreakers=["wins", {"diff": {"cap": 3}}])
    before = repr(st)
    game = g("g1", "a", "b", 3, 1)
    table([game], st)
    assert repr(st) == before and game.reading.score.final == {"home": 3, "away": 1}


# ------------------------------------------------------------------ the Masters cross-check

def test_masters_rule_reproduces_the_masters_table():
    """Masters rules (docs/stats-workflow.md): 1 point per quarter won, 3 for a win, a tied quarter and overtime
    give nothing, a tie after overtime is a tie (0 for the result), a forfeit is 1-0 in every quarter, QW is
    the tie-less quarter count; ties broken by head-to-head then point difference. Worked by hand:

      G1 Aces 20 [6,5,4,5] Bears 18 [5,6,4,3]  Q1 Aces, Q2 Bears, Q3 level, Q4 Aces -> Aces 3+2 = 5, Bears 1
      G2 Bears 30 [10,10,5,5] Cats 28 [8,9,6,5] Q1 Bears, Q2 Bears, Q3 Cats, Q4 level -> Bears 3+2 = 5, Cats 1
      G3 Cats 25 [6,6,6,7] Aces 25 [7,6,6,6] after overtime: Q1 Aces, Q4 Cats, tie -> 1 each, no win points
      G4 Cats forfeit to Aces: 4-0 in quarters -> Aces 3+4 = 7, Cats 0
      Playoff Bears beat Aces: not counted.

      Aces  13 pts  2-0-1  pf 20+25+4 = 49  pa 18+25+0 = 43  +6   QW 2+1+4 = 7   pct .833
      Bears  6 pts  1-1    pf 18+30 = 48    pa 20+28 = 48    0    QW 1+2 = 3     pct .500
      Cats   2 pts  0-2-1  pf 28+25+0 = 53  pa 30+25+4 = 59  -6   QW 1+1+0 = 2   pct .167
    """
    teams = {t: TEAMS[t] for t in "abc"}
    st = S(points={"win": 3, "tie": 0, "loss": 0}, period_points=1, forfeit={"score": "per_period"},
           tiebreakers=["head_to_head", "diff"], columns=["gp", "w", "l", "t", "pts", "pct", "pf", "pa", "diff", "pw"])
    games = [g("g1", "a", "b", [6, 5, 4, 5], [5, 6, 4, 3]),
             g("g2", "b", "c", [10, 10, 5, 5], [8, 9, 6, 5]),
             g("g3", "c", "a", [6, 6, 6, 7], [7, 6, 6, 6], extra={"home": [0], "away": [0]}, decided_in="overtime"),
             forfeit("g4", "c", "a", by="c"),
             g("p1", "b", "a", [25, 25, 25, 25], [10, 10, 10, 10], type="playoff")]
    res = compute_standings(games, teams, st, regulation_periods=4)
    assert res.problems == []
    shown = {r["team"]: [r["rank"], r["record"], *(r["display"][c] for c in ("gp", "pts", "pct", "pf", "pa", "diff", "pw"))]
             for r in res.rows}
    assert shown == {"a": [1, "2-0-1", "3", "13", ".833", "49", "43", "+6", "7"],
                     "b": [2, "1-1", "2", "6", ".500", "48", "48", "0", "3"],
                     "c": [3, "0-2-1", "3", "2", ".167", "53", "59", "−6", "2"]}
    assert [r["broke_by"] for r in res.rows] == [None, None, None]
    assert res.tiebreak_note == ("Teams level on points are ranked by head-to-head record (when they have all played "
                                 "each other), then score difference; teams still level share a rank.")


# ------------------------------------------------------------------ review fixes and edge cases

def test_a_team_playing_itself_is_a_problem_and_not_counted():
    res = table([g("g1", "a", "a", 3, 0), forfeit("g2", "b", "b", by="b")])
    assert [(p.at, p.file) for p in res.problems] == [("away", "data/test/games/g1.yml"), ("away", "data/test/games/g2.yml")]
    assert col(res, "gp") == {t: "0" for t in "abcd"}


def test_a_game_id_given_twice_is_a_problem_and_neither_copy_counts():
    res = table([g("g1", "a", "b", 3, 0), g("g1", "c", "d", 3, 0), g("g2", "a", "c", 1, 0)])
    assert [(p.level, p.at) for p in res.problems] == [("error", "game_id")] * 2
    assert col(res, "gp") == {"a": "1", "b": "0", "c": "1", "d": "0"}


def test_a_missing_final_score_is_a_problem_not_a_crash():
    res = table([g("g1", "a", "b", 3, 0, final={"home": None, "away": 2}), g("g2", "c", "d", 1, 0, final={"home": 1})])
    assert [p.at for p in res.problems] == ["sheet.final.home", "sheet.final.home"]
    assert col(res, "gp") == {t: "0" for t in "abcd"}


def test_games_behind_count_from_the_best_co_leader_and_use_a_real_minus():
    # by win %: a 1-0 and b 2-0 share first (1.000); b, the better record, is the reference, so neither shows a
    # negative number; c 0-2, d 0-1
    games = [g("g1", "a", "c", 3, 0), g("g2", "b", "d", 3, 0), g("g3", "b", "c", 3, 0)]
    res = table(games, S(rank_by="win_pct", columns=["w", "l", "pct", "gb"]))
    assert order(res) == [("a", 1), ("b", 1), ("c", 3), ("d", 3)]
    assert col(res, "gb") == {"a": "0.5", "b": "—", "c": "2", "d": "1.5"}
    # by points with a point per period: a leads on points with a worse record than b, so b is ahead in games
    st = S(points={"win": 3, "tie": 0}, period_points=1, columns=["w", "l", "pts", "gb"])
    games = [g("g1", "a", "c", [9, 9, 9, 9], [0, 0, 0, 0]), g("g2", "a", "d", [9, 9, 9, 9], [0, 0, 0, 0]),
             g("g3", "b", "c", [1, 1, 0, 0], [0, 0, 1, 1], final={"home": 3, "away": 2}),
             g("g4", "b", "d", [1, 1, 0, 0], [0, 0, 1, 1], final={"home": 3, "away": 2}),
             g("g5", "c", "a", [1, 0, 0, 0], [0, 0, 0, 0])]
    # a 2-1 with 7 + 7 + 0 = 14 points; b 2-0 with 5 + 5 = 10: b is half a game ahead of the leader
    res = table(games, st, periods=4)
    assert [r["team"] for r in res.rows][:2] == ["a", "b"] and col(res, "pts")["a"] == "14"
    assert col(res, "gb")["b"] == "−0.5" and col(res, "gb", shown=False)["b"] == -0.5


def test_four_way_tie_split_by_head_to_head_into_different_sub_groups():
    # Round robin among a-d: a beats everyone; b and c tie and both beat d. Then games with e and f bring all
    # four to 6 points (2-1-0). Head-to-head among the four: a 1.000, b .500, c .500, d .000, so it takes a out
    # on top and d out at the bottom; b and c go on to diff (b +5, c +1 from their win over e/f).
    st = S(tiebreakers=["head_to_head", "diff"])
    games = [g("g01", "a", "b", 2, 1), g("g02", "a", "c", 2, 1), g("g03", "a", "d", 2, 1), g("g04", "b", "c", 1, 1),
             g("g05", "b", "d", 2, 1), g("g06", "c", "d", 2, 1), g("g07", "b", "e", 6, 1), g("g08", "b", "f", 1, 1),
             g("g09", "c", "f", 2, 1), g("g10", "c", "e", 1, 1), g("g11", "d", "e", 2, 1), g("g12", "d", "f", 2, 1),
             g("g13", "d", "e", 2, 1)]
    res = table(games, st, teams={t: TEAMS[t] for t in "abcdef"})
    assert col(res, "pts") == {"a": "6", "b": "6", "c": "6", "d": "6", "e": "1", "f": "1"}
    assert order(res)[:4] == [("a", 1), ("b", 2), ("c", 3), ("d", 4)]
    assert [r["broke_by"] for r in res.rows][:4] == ["head_to_head", "diff", "diff", "head_to_head"]


def test_cycle_is_then_split_by_the_next_breaker():
    # a beat b, b beat c, c beat a: head-to-head is all level, so diff decides (b +4, a -1, c -3)
    games = [g("g1", "a", "b", 1, 0), g("g2", "b", "c", 5, 0), g("g3", "c", "a", 2, 0)]
    res = table(games, S(tiebreakers=["head_to_head", "diff"]), teams={t: TEAMS[t] for t in "abc"})
    assert order(res) == [("b", 1), ("a", 2), ("c", 3)] and {r["broke_by"] for r in res.rows} == {"diff"}


def test_small_seasons_one_game_a_bye_only_playoffs_and_a_single_team():
    one = table([g("g1", "a", "b", 3, 1)], S(columns=ALL_COLUMNS))
    assert order(one) == [("a", 1), ("b", 2), ("c", 2), ("d", 2)]            # c and d had a bye: level with b on 0
    rows = {r["team"]: r for r in one.rows}
    assert rows["c"]["display"]["gp"] == "0" and rows["c"]["display"]["pct"] == ".000"
    assert rows["c"]["display"]["gb"] == "0.5" and rows["b"]["display"]["gb"] == "1"
    playoffs = table([g("p1", "a", "b", 3, 1, type="playoff")], S(columns=ALL_COLUMNS))
    assert [r["rank"] for r in playoffs.rows] == [1, 1, 1, 1] and playoffs.problems == []
    single = table([], S(columns=ALL_COLUMNS), teams={"a": TEAMS["a"]})
    assert order(single) == [("a", 1)] and single.rows[0]["display"]["gb"] == "—" and not single.rows[0]["tied"]


def test_ties_false_does_not_touch_playoffs_but_a_tied_playoff_game_is_still_reported():
    res = table([g("g1", "a", "b", 3, 1), g("p1", "a", "b", 2, 2, type="playoff")], S(ties=False))
    assert [p.at for p in res.problems] == ["sheet.final.home"] and "playoff" in res.problems[0].message
    assert col(res, "gp")["a"] == "1"


def test_huge_margins_and_names_that_differ_only_in_case():
    teams = {"a": Team("a", "otters", "OTA"), "b": Team("b", "Otters", "OTB"), "c": TEAMS["c"], "d": TEAMS["d"]}
    res = table([g("g1", "b", "c", 10**6, 0), g("g2", "a", "d", 1, 0)], S(columns=["pts", "diff"]), teams=teams)
    assert order(res) == [("a", 1), ("b", 1), ("c", 3), ("d", 3)]           # same name ignoring case: then by id
    assert col(res, "diff")["b"] == "+1000000"
    capped = table([g("g1", "b", "c", 10**6, 0), g("g2", "a", "d", 1, 0)], S(tiebreakers=[{"diff": {"cap": 7}}]),
                   teams=teams)
    assert order(capped)[:2] == [("b", 1), ("a", 2)]
