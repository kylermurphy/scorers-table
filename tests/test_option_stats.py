"""Stats and boards shown only while an option is on (E23), a minimum per team game (E24), and the other sport.yml
keys of the slo-pitch core work: `display.card_head` (E25), `display.matchup` / `league.sides_order` (E26) and a
legend key that follows an option (E27). docs/stage-5-slopitch-spec.md section 6.

The sport is tests/fixtures/sports/_extra/optstats/: AB, H and AVG while `batting` is `optional` or `every_game`, BB
only with `every_game`. The league is made up here: three teams, so the teams have played different numbers of games.

    game 1  alpha 3-2 bravo   a1 1 AB 1 H, b1 4 AB 1 H
    game 2  bravo 4-1 alpha   a1 3 AB 1 H, b1 3 AB 3 H
    game 3  alpha 5-0 cy      a1 2 AB 0 H, c1 2 AB 2 H, and the spare s1 (no team) 1 AB 1 H

Alpha has played 3 games, bravo 2, cy 1. With 2 at bats a team game to rank:
    after game 1  a1 has 1 AB, needs 2: unranked;  b1 has 4 AB, needs 2: ranked (.250)
    after game 2  a1 .500 (4 AB, needs 4), b1 .571 (7 AB, needs 4)
    after game 3  a1 .333 (6 AB, needs 6), c1 1.000 (2 AB, needs 2), b1 .571; s1 (no team) needs 6, as the team that
                  has played the most (alpha): unranked
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import build
from tests.parity.site import jekyll_command, skip_unless_ci

ROOT = Path(__file__).resolve().parent.parent
SEASON, OLD = "2026-27", "2025-26"

LEAGUE = ('name: "Example Optstats League"\nsport: optstats\ntimezone: UTC\nlanding_page: false\nsample_data: false\n'
          'preview: false\n')
TEAMS = [{"id": "alpha", "name": "Alpha", "code": "ALP"}, {"id": "bravo", "name": "Bravo", "code": "BRA"},
         {"id": "cy", "name": "Cy", "code": "CY"}]
PLAYERS = [{"id": "a1", "name": "Ann A.", "team": "alpha", "number": 7}, {"id": "b1", "name": "Bob B.", "team": "bravo", "number": 9},
           {"id": "c1", "name": "Cal C.", "team": "cy", "number": 3}, {"id": "s1", "name": "Sid S.", "sub": True}]
SCHEDULE = ("game_id,date,time,home,away,venue,type,round,week,status,moved_from\n"
            "2026-11-05-1,2026-11-05,19:00,alpha,bravo,,regular,,,,\n"
            "2026-11-12-1,2026-11-12,19:00,bravo,alpha,,regular,,,,\n"
            "2026-11-19-1,2026-11-19,19:00,alpha,cy,,regular,,,,\n")
GAMES = {
    "2026-11-05-1": ("alpha", "bravo", 3, 2, {"home": [{"player": "a1", "ab": 1, "h": 1, "bb": 0}],
                                              "away": [{"player": "b1", "ab": 4, "h": 1, "bb": 1}]}),
    "2026-11-12-1": ("bravo", "alpha", 4, 1, {"home": [{"player": "b1", "ab": 3, "h": 3, "bb": 0}],
                                              "away": [{"player": "a1", "ab": 3, "h": 1, "bb": 2}]}),
    "2026-11-19-1": ("alpha", "cy", 5, 0, {"home": [{"player": "a1", "ab": 2, "h": 0, "bb": 0}, {"player": "s1", "ab": 1, "h": 1, "bb": 0}],
                                           "away": [{"player": "c1", "ab": 2, "h": 2, "bb": 1}]}),
}


def make_root(tmp: Path, *, games=tuple(GAMES), batting: str | None = None, old_batting: str | None = None,
              league_extra: str = "", extra_rows: tuple[str, ...] = ()) -> Path:
    """The fixture league: season 2026-27 (the games given), and 2025-26 with a copy of game 1 under its own
    `overrides: rules: batting` (when given), so a season override can be seen to change that season only."""
    root = tmp / "src"
    (root / "sports").mkdir(parents=True)
    shutil.copytree(ROOT / "tests/fixtures/sports/_extra/optstats", root / "sports" / "optstats",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "league.yml").write_text(LEAGUE + (f"rules: {{batting: {batting}}}\n" if batting else "") + league_extra,
                                     encoding="utf-8")
    seasons = [{"id": SEASON, "label": "2026–27", "current": True, "venue": "[Venue]"},
               {"id": OLD, "label": "2025–26", "venue": "[Venue]"}]
    if old_batting:
        seasons[1]["overrides"] = {"rules": {"batting": old_batting}}
    (root / "data").mkdir()
    (root / "data" / "seasons.yml").write_text(yaml.safe_dump(seasons, sort_keys=False, allow_unicode=True), encoding="utf-8")
    for season, ids in ((SEASON, games), (OLD, games[:1])):
        folder = root / "data" / season
        (folder / "games").mkdir(parents=True)
        (folder / "teams.yml").write_text(yaml.safe_dump(TEAMS), encoding="utf-8")
        (folder / "players.yml").write_text(yaml.safe_dump(PLAYERS), encoding="utf-8")
        rows = SCHEDULE.splitlines()
        keep = [rows[0]] + [r for r in rows[1:] if r.split(",")[0] in ids] + (list(extra_rows) if season == SEASON else [])
        (folder / "schedule.csv").write_text("\n".join(keep).replace("2026-", f"{season[:4]}-") + "\n", encoding="utf-8")
        for gid in ids:
            home, away, h, a, batters = GAMES[gid]
            new_id = gid.replace("2026-", f"{season[:4]}-")
            sheet = {"final": {"home": h, "away": a}, "batters": batters}
            game = {"game_id": new_id, "status": "final", "checked_by": "Lee M.", "home": home, "away": away, "sheet": sheet}
            (folder / "games" / f"{new_id}.yml").write_text(yaml.safe_dump(game, sort_keys=False), encoding="utf-8")
    return root


class Built:
    def __init__(self, root: Path, season: str = SEASON) -> None:
        self.root, self.season = root, season
        self.base = root / "_data" / "computed"

    def read(self, name: str, season: str | None = None):
        path = self.base / (season or self.season) / f"{name}.json" if name not in ("league", "active") else self.base / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def leaders(self):
        return self.read("leaders")

    def board(self, id_: str, season: str | None = None):
        return next((b for b in self.read("leaders", season)["boards"] if b["id"] == id_), None)

    def ids(self, season: str | None = None) -> list[str]:
        return [b["id"] for b in self.read("leaders", season)["boards"]]

    def keys(self, name: str, season: str | None = None) -> list[str]:
        return [c["key"] for c in self.read("leaders", season)["columns"]["player"][name]]


def build_it(tmp_path: Path, **kwargs) -> Built:
    root = make_root(tmp_path, **{k: v for k, v in kwargs.items() if k != "today"})
    assert build.main(["--root", str(root), "--out", str(root), "--today", kwargs.get("today", "2026-11-20")]) == 0
    return Built(root)


# ------------------------------------------------------------------ E23: stats and boards by option

def test_with_lines_kept_the_stats_and_boards_of_that_option_show(tmp_path):
    b = build_it(tmp_path)                                           # batting: optional (the sport's default)
    assert b.keys("table") == b.keys("totals") == b.keys("log") == ["gp", "ab", "h", "avg"]          # no BB
    assert b.ids() == ["avg", "hits"]                                # no walks board
    a1 = b.read("players")["a1"]["groups"]["player"]
    assert set(a1["totals"]) == {"gp", "ab", "h", "avg"} and a1["display"]["avg"] == ".333" and "bb" not in a1["display"]
    assert set(b.read("players")["a1"]["log"][0]["display"]) == {"gp", "ab", "h", "avg"}
    assert [t["group"] for t in b.leaders["tables"]] == ["player"]


def test_a_stat_a_narrower_option_list_names_shows_only_under_that_value(tmp_path):
    b = build_it(tmp_path, batting="every_game")
    assert b.keys("table") == ["gp", "ab", "h", "bb", "avg"]
    assert b.ids() == ["avg", "hits", "walks"]
    assert b.board("hits")["rows"][0]["detail"] == "7 AB, 1 BB"                          # b1 leads in hits: 4 H


def test_a_detail_naming_a_stat_that_is_off_is_left_out(tmp_path):
    b = build_it(tmp_path)                                           # hits detail names {bb}, which `optional` does not keep
    assert all(r["detail"] is None for r in b.board("hits")["rows"])
    assert b.board("avg")["rows"][0]["detail"] == "2 for 2"                                 # a board that has all it names keeps it


def test_with_only_the_batting_order_the_table_keeps_games_played_and_no_boards(tmp_path):
    b = build_it(tmp_path, batting="order")
    assert b.ids() == []
    assert b.keys("table") == ["gp"] and [t["group"] for t in b.leaders["tables"]] == ["player"]
    assert b.leaders["tables"][0]["rows"]                           # everyone who batted, listed with GP only
    assert b.read("players")["a1"]["groups"]["player"]["totals"] == {"gp": 3}


def test_with_no_batting_lines_there_is_no_group_no_table_and_no_board(tmp_path):
    b = build_it(tmp_path, batting="none")
    assert b.leaders["boards"] == [] and b.leaders["tables"] == [] and b.leaders["table"] is None
    assert b.leaders["columns"] == {}
    assert b.read("players")["a1"]["groups"] == {} and b.read("players")["a1"]["log"] == []
    assert b.read("standings")["rows"]                               # standings and results are unchanged
    assert set(b.read("games")) == set(GAMES)


def test_before_any_game_a_group_that_is_on_still_shows_its_empty_table(tmp_path):
    b = build_it(tmp_path, games=())
    assert [t["group"] for t in b.leaders["tables"]] == ["player"] and b.leaders["tables"][0]["rows"] == []
    assert [x["id"] for x in b.leaders["boards"]] == ["avg", "hits"]


def test_a_season_override_changes_that_season_only(tmp_path):
    b = build_it(tmp_path, old_batting="none")
    assert b.ids() == ["avg", "hits"] and b.keys("table") == ["gp", "ab", "h", "avg"]
    assert b.ids(OLD) == [] and b.read("leaders", OLD)["tables"] == []
    b = build_it(tmp_path / "other", batting="none", old_batting="every_game")
    assert b.ids() == [] and b.ids(OLD) == ["avg", "hits", "walks"] and b.keys("table", OLD) == ["gp", "ab", "h", "bb", "avg"]


# ------------------------------------------------------------------ E24: the minimum per team game

def ranked(b: Built):
    board = b.board("avg")
    return [(r["player"], r["display"]) for r in board["rows"]], board["unranked"]


def test_early_in_the_season_the_minimum_is_for_the_games_played_so_far(tmp_path):
    b = build_it(tmp_path, games=("2026-11-05-1",))
    rows, unranked = ranked(b)
    assert rows == [("b1", ".250")] and unranked == ["a1"]           # a1: 1 AB, alpha has played 1 game, needs 2


def test_it_grows_with_each_game_the_team_plays(tmp_path):
    b = build_it(tmp_path, games=("2026-11-05-1", "2026-11-12-1"))
    rows, unranked = ranked(b)
    assert rows == [("b1", ".571"), ("a1", ".500")] and unranked == []     # a1: 4 AB in 2 games, needs 4


def test_late_in_the_season_a_player_on_a_team_with_fewer_games_needs_fewer(tmp_path):
    b = build_it(tmp_path)
    rows, unranked = ranked(b)
    # c1: cy has played 1 game, so 2 AB is enough; a1: alpha has played 3, so 6 AB are needed (and has 6)
    assert rows == [("c1", "1.000"), ("b1", ".571"), ("a1", ".333")]
    assert unranked == ["s1"]                                        # no team: 2 x alpha's 3 games, s1 has 1 AB
    assert b.board("avg")["min"] == {"value": 2, "placeholder": True, "note": "Minimum [placeholder] at bats per team game to rank."}


def test_a_spare_with_no_team_needs_the_minimum_of_the_team_that_has_played_the_most(tmp_path, monkeypatch):
    """A spare (no team) 2 for 2 would lead with the plain minimum (2 AB); per team game it needs 2 x 3 (alpha's
    games), as strict as the strictest regular, so a few at bats never top the board."""
    home, away, h, a, batters = GAMES["2026-11-19-1"]
    batters = {"home": [batters["home"][0], {"player": "s1", "ab": 2, "h": 2, "bb": 0}], "away": batters["away"]}
    monkeypatch.setitem(GAMES, "2026-11-19-1", (home, away, h, a, batters))
    rows, unranked = ranked(build_it(tmp_path))
    assert "s1" not in [p for p, _ in rows] and unranked == ["s1"]
    rows, unranked = ranked(build_it(tmp_path / "early", games=("2026-11-19-1",)))     # every team 1 game or none
    assert ("s1", "1.000") in rows and unranked == []                                  # 2 AB is then enough


def test_a_league_can_raise_the_per_game_minimum(tmp_path):
    b = build_it(tmp_path, league_extra="stats: {minimums: {min_ab: 3}}\n")
    rows, unranked = ranked(b)
    assert rows == [("b1", ".571")] and unranked == ["a1", "c1", "s1"]     # a1 needs 9 AB, b1 6, c1 3 (has 2)


# ------------------------------------------------------------------ E25, E26, E27: league.json

def test_card_head_and_matchup_come_from_sport_yml_and_set_the_sides_order(tmp_path):
    league = build_it(tmp_path).read("league")
    assert league["display"]["card_head"] == "status_surface" and league["display"]["matchup"] == "at"
    assert league["sides_order"] == ["away", "home"]
    assert "results_legend" not in league["display"]


def test_a_legend_key_shows_the_leagues_value_of_the_option(tmp_path):
    legend = build_it(tmp_path).read("league")["results_legend"]
    assert legend == [{"kind": "limit", "text": "Inning ended at the run limit.", "mark": "5"},
                      {"kind": "x", "text": "Not needed."}]
    legend = build_it(tmp_path / "seven", league_extra="rules: {run_limit: 7}\n").read("league")["results_legend"]
    assert legend[0]["mark"] == "7" and "mark_option" not in legend[0] and "mark" not in legend[1]


def test_every_line_score_has_the_extras_defaults(tmp_path):
    """E20: `extras` is an empty list on the line score and on each row when the sport gives none."""
    from scripts.core.compute_games import _line_score
    from types import SimpleNamespace
    ctx = SimpleNamespace(spec={"words": {"period": {"one": "Inning"}}})
    given = {"line_score": {"columns": [], "rows": {"home": {"cells": [], "total": 3, "extras": [5, 0]},
                                                    "away": {"cells": [], "total": 2}}, "extras": [
                                                        {"label": "H", "title": "Hits"}, {"label": "E", "title": "Errors"}]}}
    ls = _line_score(ctx, given)
    assert ls["extras"] == [{"label": "H", "title": "Hits"}, {"label": "E", "title": "Errors"}]
    assert ls["rows"]["home"]["extras"] == [5, 0] and ls["rows"]["away"]["extras"] == []
    plain = _line_score(ctx, {"line_score": {"columns": [], "rows": {"home": {"cells": []}, "away": {"cells": []}}}})
    assert plain["extras"] == [] and plain["rows"]["home"]["extras"] == [] and plain["rows"]["home"]["extra"] is None


# ------------------------------------------------------------------ the pages (needs Jekyll)

def render(built: Built, tmp: Path) -> Path:
    command = jekyll_command()
    if command is None:
        skip_unless_ci("this test needs Ruby, Bundler and the gems")
    tmp.mkdir(parents=True, exist_ok=True)
    src = tmp / "site-src"
    for name in ("_config.yml", "_layouts", "_includes", "assets", "index.html", "schedule", "stats", "teams", "archive", "rules", "404.html"):
        path = ROOT / name
        shutil.copytree(path, src / name) if path.is_dir() else (src.mkdir(exist_ok=True), shutil.copy(path, src / name))
    shutil.copytree(built.root / "_data", src / "_data")
    for folder in ("_games", "_players", "_teams", "_archive"):
        if (built.root / folder).is_dir():
            shutil.copytree(built.root / folder, src / folder)
    shutil.copy(built.root / "league.yml", src / "league.yml")
    out = tmp / "site"
    proc = subprocess.run([*command, "build", "--source", str(src), "--destination", str(out), "--quiet"], cwd=ROOT,
                          capture_output=True, text=True, env=dict(os.environ))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return out


def page(out: Path, path: str) -> str:
    return (out / path.strip("/") / "index.html").read_text(encoding="utf-8")


@pytest.mark.jekyll
def test_the_pages_follow_the_option(tmp_path):
    full = render(build_it(tmp_path / "full", old_batting="none"), tmp_path / "full-site")
    assert "Hitting</h2>" in page(full, "") and "Batting avg" in page(full, "")             # Home: the Leaders section
    stats = page(full, "stats")
    assert "Batting avg" in stats and "All players" in stats and ">AVG</abbr>" in stats and ">BB</abbr>" not in stats
    assert "Roster" in page(full, "teams/alpha") and "Season totals</h2>" in page(full, "players/a1")
    old = page(full, f"archive/{OLD}")
    assert "Hitting</h2>" not in old and "No stats were kept" not in old                  # that season keeps no batting lines
    assert "Standings</h2>" in old and "Results</h2>" in old

    order = render(build_it(tmp_path / "order", batting="order"), tmp_path / "order-site")
    assert "Hitting</h2>" not in page(order, "") and "Hitting</h2>" not in page(order, "stats")
    assert "All players" in page(order, "stats") and ">AVG</abbr>" not in page(order, "stats")
    assert "Roster" in page(order, "teams/alpha")

    none = render(build_it(tmp_path / "none", batting="none"), tmp_path / "none-site")
    assert "Hitting</h2>" not in page(none, "")
    stats = page(none, "stats")
    assert "All players" not in stats and "Hitting</h2>" not in stats and "Standings</h2>" in stats     # the table moves to Stats
    assert "Roster" not in page(none, "teams/alpha") and "Results</h2>" in page(none, "teams/alpha")
    assert "Season totals</h2>" not in page(none, "players/a1") and "Game log</h2>" not in page(none, "players/a1")


def test_calendar_summaries_follow_the_matchup(tmp_path):
    """E26: with `matchup: at` the calendar names the visitors first ("Bravo at Alpha"), as the pages do."""
    b = build_it(tmp_path)
    text = (b.root / "calendar" / "league.ics").read_text(encoding="utf-8").replace("\n ", "")
    assert "SUMMARY:Bravo at Alpha" in text and " vs " not in text
    assert "Final: Bravo 2\\, Alpha 3." in text                     # the result in the description, visitors first too


def test_a_game_pages_title_and_description_put_the_visitors_first(tmp_path):
    """E26: the stub's `title` (the browser tab, the share tags) and `description` follow the matchup."""
    b = build_it(tmp_path)
    stub = yaml.safe_load((b.root / "_games" / "2026-11-05-1.md").read_text(encoding="utf-8").split("---")[1])
    assert stub["title"] == "Bravo at Alpha"
    assert stub["description"].startswith("Final: Bravo 2, Alpha 3 on ")


@pytest.mark.jekyll
def test_cancelled_and_moved_notes_on_the_schedule_put_the_visitors_first(tmp_path):
    rows = ("2026-11-26-1,2026-11-26,19:00,cy,bravo,,regular,,,cancelled,",
            "2026-12-03-1,2026-12-03,19:00,bravo,cy,,regular,,,,2026-11-28")
    root = make_root(tmp_path, extra_rows=rows)
    assert build.main(["--root", str(root), "--out", str(root), "--today", "2026-11-20"]) == 0
    schedule = page(render(Built(root), tmp_path / "site"), "schedule")
    assert "Cancelled: Bravo at Cy.</p>" in schedule
    assert re.search(r"Cy at Bravo was moved from [^<]+\.</p>", schedule)
    assert " vs " not in schedule
