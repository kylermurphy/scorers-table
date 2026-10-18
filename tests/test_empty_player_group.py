"""A sport whose player group counts nothing (`stats.player: []`, curling's case: a player only has games played)
works end to end: the Stats table shows GP only, a game log has no stat columns, no player board is made, and the
pages build. The throwaway sport is tests/fixtures/sports/_extra/rinks (one folder down, so the tests that list
tests/fixtures/sports/ do not see it)."""
import json
import re
import shutil
import subprocess
import os
from pathlib import Path

import pytest

from scripts import build, make_sample
from tests.parity.site import jekyll_command, skip_unless_ci

ROOT = Path(__file__).resolve().parent.parent
EXTRA_SPORTS = ROOT / "tests" / "fixtures" / "sports" / "_extra"
SOURCE = ["_config.yml", "_layouts", "_includes", "assets", "index.html", "schedule", "stats", "teams", "archive",
          "rules", "404.html"]
SEASON = "sample-2026-27"


@pytest.fixture(autouse=True)
def not_github(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def rinks_root(tmp: Path, *, source: bool = False) -> Path:
    """A throwaway repository whose league plays the Rinks sport, with its made-up sample seasons written."""
    root = tmp / "repo"
    root.mkdir()
    shutil.copytree(EXTRA_SPORTS, root / "sports", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "data").mkdir()
    shutil.copy(ROOT / "data" / "seasons.yml", root / "data" / "seasons.yml")
    shutil.copytree(ROOT / "data" / "2026-27", root / "data" / "2026-27")
    text = (ROOT / "league.yml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^sport: .*$", "sport: rinks", text)
    text = re.sub(r"(?m)^name: .*$", 'name: "Example Rinks League"', text)
    (root / "league.yml").write_text(text, encoding="utf-8")
    if source:
        for name in SOURCE:
            src = ROOT / name
            shutil.copytree(src, root / name) if src.is_dir() else shutil.copy(src, root / name)
    make_sample.write_all(root, make_sample.generate_all(root))
    return root


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = rinks_root(tmp_path_factory.mktemp("rinks"))
    out = root / "out"
    assert build.main(["--root", str(root), "--out", str(out), "--today", "2026-11-20"]) == 0
    return out


def computed(out: Path, name: str):
    return json.loads((out / "_data" / "computed" / SEASON / name).read_text(encoding="utf-8"))


def test_the_sample_loads_without_a_problem(tmp_path):
    assert make_sample.run_loader(rinks_root(tmp_path)) == []


def test_the_stats_table_is_games_played_only_and_no_board_is_made(built):
    leaders = computed(built, "leaders.json")
    assert leaders["boards"] == []
    assert [c["key"] for c in leaders["table"]["columns"]] == ["gp"]
    assert leaders["table"]["rows"], "everyone who played is still listed"
    assert not any(c["key_col"] for c in leaders["table"]["columns"])


def test_the_log_and_totals_columns_hold_games_played_and_nothing_else(built):
    columns = computed(built, "leaders.json")["columns"]["player"]
    assert {name: [c["key"] for c in cols] for name, cols in columns.items()} == {
        "table": ["gp"], "totals": ["gp"], "log": ["gp"]}


def test_a_player_has_games_played_a_game_log_and_no_stats(built):
    players = computed(built, "players.json")
    played = [p for p in players.values() if p["log"]]
    assert played
    for player in played:
        assert player["groups"]["player"]["totals"] == {"gp": len(player["log"])}
        assert all(entry["display"] == {"gp": "1"} for entry in player["log"])
        assert player["groups"]["player"]["ranks"] == {}
    assert {p["position"] for p in players.values() if p["team"]} == {"lead", "second", "skip"}
    assert all(p["number"] is None for p in players.values())


@pytest.fixture(scope="module")
def jekyll():
    command = jekyll_command()
    if command is None:
        skip_unless_ci("this test needs Ruby, Bundler and the gems: run `bundle install`; CI always runs it")
    return command


@pytest.mark.jekyll
def test_the_pages_render_with_games_played_only(tmp_path, jekyll):
    root = rinks_root(tmp_path, source=True)
    assert build.main(["--root", str(root), "--out", str(root), "--today", "2026-11-20"]) == 0
    out = tmp_path / "site"
    proc = subprocess.run([*jekyll, "build", "--source", str(root), "--destination", str(out), "--config",
                           str(root / "_config.yml"), "--quiet"], cwd=ROOT, capture_output=True, text=True,
                          env=dict(os.environ))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    pages = {p: p.read_text(encoding="utf-8") for p in out.rglob("*.html")}
    assert not [p for p, html in pages.items() if "Liquid error" in html or "Liquid syntax error" in html]
    stats = (out / "stats" / "index.html").read_text(encoding="utf-8")
    table = stats[stats.index("All players"):]
    table = table[table.index("<thead>"):table.index("</thead>")]
    assert len(re.findall(r"<th[ >]", table)) == 3, table          # Player, Team, GP
    assert "Games played" in table
    player_pages = sorted((out / "players").glob("*/index.html"))
    assert player_pages
    log = next(h for h in (p.read_text(encoding="utf-8") for p in player_pages) if "Game log" in h and "<tbody>" in h)
    header = log[log.index("Game log"):]
    header = header[header.index("<thead>"):header.index("</thead>")]
    assert len(re.findall(r"<th[ >]", header)) == 4, header          # Date, Opponent, Result, Score: no stat column
