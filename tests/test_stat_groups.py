"""More than one stat group (hockey's skaters and goalies), against the two-group test sport in
tests/fixtures/sports/twogroup/ (docs/stage-5-hockey-spec.md, E12-E15 and E19).

The league is made up here: two teams, a skater and goalie of each, and `flex`, a player of Bravo who is a skater in
one game and the goalie in another (so he has both groups and two game logs). The numbers were worked out by hand:

    game 1  Alpha 4-3 Bravo, decided in a shootout   goalies: gus-t (Alpha) ga 3 sa 30, ben-r (Bravo) ga 4 sa 20
    game 2  Alpha 2-0 Bravo                          goalies: zed-q (Alpha) ga 0 (no shots counted), flex ga 2 sa 12
    game 3  Bravo 1-1 Alpha                          goalies: ben-r ga 1 sa 14, gus-t ga 1 sa 20

so GAA: zed-q 0.00 (1 GP), gus-t 2.00 (2 GP), flex 2.00 (1 GP), ben-r 2.50 (2 GP); SV%: gus-t .920 (4 of 50),
ben-r .853, flex .833, and none for zed-q (no shots).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import build
from tests.parity.site import jekyll_command, skip_unless_ci

ROOT = Path(__file__).resolve().parent.parent
SEASON = "2026-27"

LEAGUE = 'name: "Example Twogroup League"\nsport: twogroup\ntimezone: UTC\nlanding_page: false\nsample_data: false\nstats: {minimums: {goalie_min_games: 2}}\n'
TEAMS = [{"id": "alpha", "name": "Alpha", "code": "ALP"}, {"id": "bravo", "name": "Bravo", "code": "BRA"}]
PLAYERS = [
    {"id": "ann-b", "name": "Ann B.", "team": "alpha", "number": 7}, {"id": "gus-t", "name": "Gus T.", "team": "alpha", "number": 31},
    {"id": "zed-q", "name": "Zed Q.", "team": "alpha", "number": 1},
    {"id": "cy-d", "name": "Cy D.", "team": "bravo", "number": 9}, {"id": "ben-r", "name": "Ben R.", "team": "bravo", "number": 30},
    {"id": "flex", "name": "Flex F.", "team": "bravo", "number": 12}, {"id": "idle-i", "name": "Idle I.", "team": "bravo"},
]
SCHEDULE = ("game_id,date,time,home,away,venue,type,round,week,status,moved_from\n"
            "2026-11-05-1,2026-11-05,19:00,alpha,bravo,,regular,,,,\n"
            "2026-11-12-1,2026-11-12,19:00,alpha,bravo,,regular,,,,\n"
            "2026-11-19-1,2026-11-19,19:00,bravo,alpha,,regular,,,,\n")
GAMES = {
    "2026-11-05-1": {"final": {"home": 4, "away": 3}, "decided": "shootout",
                     "skaters": {"home": [{"player": "ann-b", "g": 2, "a": 1}], "away": [{"player": "cy-d", "g": 1}, {"player": "flex", "g": 1, "a": 1}]},
                     "goalies": {"home": [{"player": "gus-t", "ga": 3, "sa": 30}], "away": [{"player": "ben-r", "ga": 4, "sa": 20}]}},
    "2026-11-12-1": {"final": {"home": 2, "away": 0},
                     "skaters": {"home": [{"player": "ann-b", "g": 2}]},
                     "goalies": {"home": [{"player": "zed-q", "ga": 0}], "away": [{"player": "flex", "ga": 2, "sa": 12}]}},
    "2026-11-19-1": {"final": {"home": 1, "away": 1},
                     "skaters": {"home": [{"player": "cy-d", "g": 1}], "away": [{"player": "ann-b", "a": 1, "g": 1}]},
                     "goalies": {"home": [{"player": "ben-r", "ga": 1, "sa": 14}], "away": [{"player": "gus-t", "ga": 1, "sa": 20}]}},
}


def make_root(tmp: Path) -> Path:
    root = tmp / "src"
    (root / "sports").mkdir(parents=True)
    shutil.copytree(ROOT / "tests/fixtures/sports/twogroup", root / "sports" / "twogroup", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "league.yml").write_text(LEAGUE, encoding="utf-8")
    data = root / "data" / SEASON
    (data / "games").mkdir(parents=True)
    (root / "data" / "seasons.yml").write_text(f'- {{id: {SEASON}, label: "2026–27", current: true, venue: "[Venue]"}}\n', encoding="utf-8")
    (data / "teams.yml").write_text(yaml.safe_dump(TEAMS), encoding="utf-8")
    (data / "players.yml").write_text(yaml.safe_dump(PLAYERS), encoding="utf-8")
    (data / "schedule.csv").write_text(SCHEDULE, encoding="utf-8")
    for gid, sheet in GAMES.items():
        game = {"game_id": gid, "status": "final", "checked_by": "Lee M.", "home": "alpha" if gid != "2026-11-19-1" else "bravo",
                "away": "bravo" if gid != "2026-11-19-1" else "alpha", "sheet": sheet}
        (data / "games" / f"{gid}.yml").write_text(yaml.safe_dump(game, sort_keys=False), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = make_root(tmp_path_factory.mktemp("twogroup"))
    assert build.main(["--root", str(root), "--out", str(root), "--today", "2026-11-20"]) == 0
    base = root / "_data" / "computed" / SEASON
    read = lambda name: json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
    return type("Built", (), {"root": root, "players": read("players"), "leaders": read("leaders"), "games": read("games")})


def board(built, id_):
    return next(b for b in built.leaders["boards"] if b["id"] == id_)


# ------------------------------------------------------------------ E12: order asc

def test_an_asc_board_lists_the_lowest_first_ranks_a_zero_and_shares_ties(built):
    b = board(built, "gaa")
    assert b["order"] == "asc"
    assert [(r["player"], r["rank"], r["display"]) for r in b["rows"]] == [
        ("zed-q", 1, "0.00"), ("flex", 2, "2.00"), ("gus-t", 2, "2.00"), ("ben-r", 4, "2.50")]
    assert board(built, "g")["order"] == "desc"


def test_a_rate_with_no_value_is_never_ranked(built):
    assert [r["player"] for r in board(built, "sv")["rows"]] == ["gus-t", "ben-r", "flex"]          # zed-q: no shots


def test_the_minimum_applies_to_an_asc_board(built):
    b = board(built, "gaa_min")
    assert [(r["player"], r["rank"]) for r in b["rows"]] == [("gus-t", 1), ("ben-r", 2)]
    assert b["unranked"] == ["flex", "zed-q"] and b["min"]["note"] == "Goalies need 2 games played to rank."


def test_a_players_rank_follows_the_board_and_the_stats_table_sorts_the_same_way(built):
    assert built.players["zed-q"]["groups"]["goalie"]["ranks"]["gaa"] == 1
    assert built.players["ben-r"]["groups"]["goalie"]["ranks"]["gaa"] == 4
    goalies = next(t for t in built.leaders["tables"] if t["group"] == "goalie")
    assert goalies["rows"] == ["zed-q", "flex", "gus-t", "ben-r"]                    # lowest GAA first; ties by name


# ------------------------------------------------------------------ E13: format dot

def test_a_dot_rate_drops_its_leading_zero(built):
    goalie = built.players["gus-t"]["groups"]["goalie"]
    assert goalie["display"]["sv"] == ".920" and goalie["totals"]["sv"] == 0.92 and goalie["display"]["gaa"] == "2.00"
    assert built.players["zed-q"]["groups"]["goalie"]["display"]["sv"] == "—"


# ------------------------------------------------------------------ E14: stat groups

def test_there_is_one_table_per_group_with_its_label_and_its_own_columns(built):
    tables = built.leaders["tables"]
    assert [(t["group"], t["label"]) for t in tables] == [("skater", "Skaters"), ("goalie", "Goalies")]
    assert built.leaders["table"] == tables[0]
    assert [c["key"] for c in tables[0]["columns"]] == ["gp", "g", "a"]
    assert [c["key"] for c in tables[1]["columns"]] == ["gp", "ga", "sa", "gaa", "sv"]
    assert tables[0]["rows"] == ["ann-b", "cy-d", "flex"]                            # goals 5, 2, 1
    assert [c["key"] for c in built.leaders["columns"]["skater"]["log"]] == ["gp", "g", "a"]


def test_a_rate_that_names_a_group_is_worked_out_for_that_group_only(built):
    assert "gaa" not in built.players["ann-b"]["groups"]["skater"]["display"]
    assert "gaa" in built.players["gus-t"]["groups"]["goalie"]["display"]


def test_boards_name_their_group_from_stats_labels(built):
    assert board(built, "g")["group_label"] == "Skaters" and board(built, "gaa")["group_label"] == "Goalies"


def test_a_player_in_both_groups_has_both_totals_and_two_logs(built):
    flex = built.players["flex"]
    assert set(flex["groups"]) == {"skater", "goalie"}
    assert [(e["game"], e["group"]) for e in flex["log"]] == [("2026-11-05-1", "skater"), ("2026-11-12-1", "goalie")]
    assert [set(e["display"]) for e in flex["log"]] == [{"gp", "g", "a"}, {"gp", "ga", "sa", "gaa", "sv"}]
    assert flex["log"][1]["display"]["sv"] == ".833"


# ------------------------------------------------------------------ E15: board columns

def test_board_columns_fill_the_cells_and_mark_the_key_column(built):
    b = board(built, "g")
    assert b["columns"] == [{"key": "g", "label": "G", "title": "Goals", "key_col": True},
                            {"key": "a", "label": "A", "title": "Assists", "key_col": False}]
    assert b["rows"][0]["player"] == "ann-b" and b["rows"][0]["cells"] == {"g": "5", "a": "2"}
    assert board(built, "gaa")["columns"] is None and board(built, "gaa")["rows"][0]["cells"] is None


# ------------------------------------------------------------------ E19: the shootout sub line

def test_a_game_decided_in_a_shootout_says_who_won_it_not_by_how_much(built):
    assert built.games["2026-11-05-1"]["final"]["sub"] == "Alpha won the shootout"
    assert built.games["2026-11-12-1"]["final"]["sub"] == "Alpha by 2"
    assert built.games["2026-11-19-1"]["final"]["sub"] == "Tied 1–1"


# ------------------------------------------------------------------ the pages (needs Jekyll)

@pytest.mark.jekyll
def test_the_pages_print_one_table_and_one_log_per_group(built, tmp_path):
    command = jekyll_command()
    if command is None:
        skip_unless_ci("this test needs Ruby, Bundler and the gems")
    root = tmp_path / "site-src"
    for name in ("_config.yml", "_layouts", "_includes", "assets", "index.html", "schedule", "stats", "teams", "archive", "rules", "404.html"):
        src = ROOT / name
        shutil.copytree(src, root / name) if src.is_dir() else (root.mkdir(exist_ok=True), shutil.copy(src, root / name))
    shutil.copytree(built.root / "_data", root / "_data")
    for folder in ("_games", "_players", "_teams", "_archive"):
        if (built.root / folder).is_dir():
            shutil.copytree(built.root / folder, root / folder)
    shutil.copy(built.root / "league.yml", root / "league.yml")
    out = tmp_path / "site"
    proc = subprocess.run([*command, "build", "--source", str(root), "--destination", str(out), "--quiet"], cwd=ROOT,
                          capture_output=True, text=True, env=dict(os.environ))
    assert proc.returncode == 0, proc.stdout + proc.stderr

    def page(path):
        return (out / path.strip("/") / "index.html").read_text(encoding="utf-8")

    stats = page("stats")
    assert stats.count('<p class="st-label st-leader-group">Skaters</p>') == 1 and stats.count("Goalies</p>") >= 1
    assert "<caption class=\"st-visually-hidden\">All players, skaters</caption>" in stats
    assert "<caption class=\"st-visually-hidden\">All players, goalies</caption>" in stats
    team = page("teams/bravo")
    assert "Roster, skaters" in team and "Roster, goalies" in team
    flex = page("players/flex")
    assert flex.count("Game log</caption>") == 2 and flex.count(">SV%</abbr>") >= 2
    assert page("players/ann-b").count("Game log</caption>") == 1 and "Skaters</p>" not in page("players/ann-b")
