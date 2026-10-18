"""Tests for scripts/build.py and the compute and write stages behind it (docs/stage-4-spec.md section 4).

Every test builds a throwaway repository (a copy of sports/ and data/ and a league.yml) into a throwaway output
folder and reads what came out, so nothing here touches the real `_data/computed/`. The golden files
(test_golden.py) pin the exact JSON; these tests pin the rules: the sample switch, today / `as_of` and the next
and latest day, the archive, unique game ids, which seasons get which stub pages and that old ones are wiped, the
atomic write, `--check`, `--json`, annotations, exit codes, and that the computed JSON has every key the
includes read (the shape-conformance test against scripts/design_system/contract.py).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build
from scripts.core import writer
from tests.conftest import set_landing_page
from tests.stub_root import use_the_stub

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ a throwaway repository

def make_repo(tmp_path: Path, *, sample_data: bool = True, real_season: bool = False) -> Path:
    """A copy of sports/, data/ and league.yml. With `real_season` the real season (2026-27) holds a copy of the
    sample 2026-27 games, so `sample_data: false` shows something."""
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(ROOT / "sports", root / "sports")
    shutil.copytree(ROOT / "data", root / "data")
    shutil.copy(ROOT / "league.yml", root / "league.yml")
    use_the_stub(root)
    text = set_landing_page((root / "league.yml").read_text(encoding="utf-8"))
    text = text.replace("sample_data: true", f"sample_data: {str(sample_data).lower()}")
    (root / "league.yml").write_text(text, encoding="utf-8")
    if real_season:
        shutil.rmtree(root / "data" / "2026-27")
        shutil.copytree(root / "data" / "sample-2026-27", root / "data" / "2026-27")
    return root


def run(root: Path, out: Path, *flags: str, capsys=None, today: str | None = "2026-11-20"):
    """Run the build in this process. Returns (exit code, stdout, stderr)."""
    args = ["--root", str(root), "--out", str(out), *flags]
    if today:
        args += ["--today", today]
    code = build.main(args)
    captured = capsys.readouterr() if capsys else None
    return (code, captured.out, captured.err) if captured else (code, "", "")


def computed(out: Path, *parts: str):
    return json.loads(Path(out, "_data", "computed", *parts).read_text(encoding="utf-8"))


def tree(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True)
def not_github(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


@pytest.fixture(scope="module")
def sample_out(tmp_path_factory):
    """One sample build (the stub's sample, sample mode), shared by the tests that only read it."""
    base = tmp_path_factory.mktemp("sample_root")
    out = tmp_path_factory.mktemp("sample_out")
    assert build.main(["--root", str(make_repo(base)), "--out", str(out), "--today", "2026-11-20"]) == 0
    return out


# ------------------------------------------------------------------ the sample switch

def test_sample_data_shows_the_stand_in_season_and_archives_the_other_sample(sample_out):
    active = computed(sample_out, "active.json")
    assert active == {"season": "sample-2026-27", "sample_mode": True, "archive": ["sample-2025-26"],
                      "today": "2026-11-20", "preview": False, "preview_kind": "", "preview_sport": "",
                      "sport_previews": []}
    assert [s["id"] for s in computed(sample_out, "seasons.json")] == ["sample-2026-27", "sample-2025-26"]
    assert sorted(p.name for p in (sample_out / "_data" / "computed").iterdir() if p.is_dir()) == [
        "sample-2025-26", "sample-2026-27"]            # the real season is not on the site while the sample is


def test_real_data_shows_the_current_season_and_no_sample(tmp_path, capsys):
    root, out = make_repo(tmp_path, sample_data=False), tmp_path / "out"
    code, _, _ = run(root, out, capsys=capsys, today="2026-10-01")
    assert code == 0
    assert computed(out, "active.json") == {"season": "2026-27", "sample_mode": False, "archive": [],
                                            "today": "2026-10-01", "preview": False, "preview_kind": "",
                                            "preview_sport": "", "sport_previews": []}
    assert computed(out, "archive.json") == []
    assert list((out / "_archive").iterdir()) == []
    assert computed(out, "2026-27", "teams.json") == {}              # a new league's empty season still builds
    assert computed(out, "2026-27", "schedule.json")["days"] == []
    assert computed(out, "league.json")["tagline"] == "Stub · 2026–27"


def test_sample_flag_forces_the_sample_and_marks_a_preview(tmp_path, capsys):
    root, out = make_repo(tmp_path, sample_data=False), tmp_path / "out"
    code, _, _ = run(root, out, "--sample", capsys=capsys)
    assert code == 0
    active = computed(out, "active.json")
    assert (active["season"], active["sample_mode"], active["preview"]) == ("sample-2026-27", True, True)
    assert active["preview_kind"] == "league"


def test_sample_flag_is_not_a_preview_when_the_site_already_shows_the_sample(tmp_path, capsys):
    root, out = make_repo(tmp_path, sample_data=True), tmp_path / "out"
    run(root, out, "--sample", capsys=capsys)
    assert computed(out, "active.json")["preview"] is False


def test_sample_data_without_a_stand_in_season_is_a_problem(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    seasons = (root / "data" / "seasons.yml").read_text(encoding="utf-8").replace("  stands_in_for: 2026-27\n", "")
    (root / "data" / "seasons.yml").write_text(seasons, encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1 and "no sample season standing in" in err and not out.exists()


# ------------------------------------------------------------------ today, as_of, the next and latest day

def days_by_n(schedule: dict) -> dict:
    return {d["n"]: d for d in schedule["days"]}


def test_a_sample_season_is_always_on_its_as_of_date(sample_out, tmp_path, capsys):
    schedule = computed(sample_out, "sample-2026-27", "schedule.json")
    days = days_by_n(schedule)
    assert days[schedule["latest"]]["date"] == "2026-11-19" and days[schedule["next"]]["date"] == "2026-11-26"
    out = tmp_path / "other_day"
    run(make_repo(tmp_path), out, capsys=capsys, today="2030-06-01")           # --today is ignored by a sample
    again = computed(out, "sample-2026-27", "schedule.json")
    assert (again["latest"], again["next"]) == (schedule["latest"], schedule["next"])
    assert computed(out, "active.json")["today"] == "2026-11-20"


@pytest.mark.parametrize("today,next_date,latest_date", [
    ("2026-11-20", "2026-11-26", "2026-11-19"),
    ("2026-11-26", "2026-11-26", "2026-11-19"),         # game day itself is still the next day until its sheets are in
    ("2026-12-05", "2026-12-10", "2026-11-19"),
    ("2027-02-01", None, "2026-11-19"),                 # nothing left to play: no next day
])
def test_a_real_season_follows_today(tmp_path, capsys, today, next_date, latest_date):
    root, out = make_repo(tmp_path, sample_data=False, real_season=True), tmp_path / "out"
    code, _, _ = run(root, out, capsys=capsys, today=today)
    assert code == 0
    schedule = computed(out, "2026-27", "schedule.json")
    days = days_by_n(schedule)
    assert (days[schedule["next"]]["date"] if schedule["next"] else None) == next_date
    assert days[schedule["latest"]]["date"] == latest_date
    next_day = days.get(schedule["next"])
    if next_day:
        assert next_day["eyebrow"] == "Next game day" and next_day["state"] in ("upcoming", "partial")


def test_next_day_skips_a_cancelled_day_and_a_day_whose_sheets_are_in(tmp_path, capsys):
    root, out = make_repo(tmp_path, sample_data=False, real_season=True), tmp_path / "out"
    path = root / "data" / "2026-27" / "schedule.csv"
    lines = [line.replace("regular,,,,", "regular,,,cancelled,") if line.startswith("2026-11-26") else line
             for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(root, out, capsys=capsys, today="2026-11-20")
    schedule = computed(out, "2026-27", "schedule.json")
    days = days_by_n(schedule)
    assert days[schedule["next"]]["date"] == "2026-12-03"
    cancelled = next(d for d in schedule["days"] if d["date"] == "2026-11-26")
    assert cancelled["state"] == "cancelled" and cancelled["byes"] == []
    # today is the day of the (all played) 2026-11-12 games: the next day is still a later one
    run(root, out, capsys=capsys, today="2026-11-12")
    assert days_by_n(computed(out, "2026-27", "schedule.json"))[
        computed(out, "2026-27", "schedule.json")["next"]]["date"] == "2026-11-19"


def test_schedule_days_states_byes_and_playoffs_apart(sample_out):
    schedule = computed(sample_out, "sample-2026-27", "schedule.json")
    by_date = {(d["date"], d["type"]): d for d in schedule["days"]}
    assert by_date[("2026-10-29", "regular")]["state"] == "played"        # one game played, the other cancelled
    assert by_date[("2026-11-19", "regular")]["state"] == "partial"       # one sheet still to come
    assert by_date[("2026-11-26", "regular")]["state"] == "upcoming"
    assert by_date[("2026-11-26", "regular")]["byes"] == ["moose"]
    cancelled = next(g for g in by_date[("2026-10-29", "regular")]["games"] if g["status"] == "cancelled")
    assert cancelled["id"] == "2026-10-29-2" and cancelled["played"] is False
    moved = next(g for d in schedule["days"] for g in d["games"] if g["id"] == "2026-12-17-2")
    assert moved["moved_from_display"] == "Thu Dec 17"
    assert [d["date"] for d in schedule["days"] if d["type"] == "playoff"] == ["2027-01-07", "2027-01-14"]
    playoff = by_date[("2027-01-07", "playoff")]
    assert playoff["byes"] == [] and playoff["label"] == "Semifinal"
    assert (playoff["games"][0]["home"], playoff["games"][0]["home_name"]) == ("1st", "1st")
    assert playoff["games"][0]["teams_known"] is False
    assert [d["n"] for d in schedule["days"]] == list(range(1, len(schedule["days"]) + 1))


def test_results_list_the_played_days_newest_first(sample_out):
    results = computed(sample_out, "sample-2026-27", "results.json")
    schedule = computed(sample_out, "sample-2026-27", "schedule.json")
    assert results[0]["day"] == schedule["latest"] and results[0]["games"] == ["2026-11-19-1"]
    assert [r["day"] for r in results] == sorted((r["day"] for r in results), reverse=True)
    assert sum(len(r["games"]) for r in results) == len(computed(sample_out, "sample-2026-27", "games.json"))


def test_times_are_pm_only_when_every_game_is(sample_out, tmp_path, capsys):
    assert computed(sample_out, "sample-2026-27", "schedule.json")["all_times_pm"] is True
    assert "All times PM." in days_by_n(computed(sample_out, "sample-2026-27", "schedule.json"))[7]["foot"]
    root, out = make_repo(tmp_path), tmp_path / "out"
    path = root / "data" / "sample-2026-27" / "schedule.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("2026-11-26,19:00", "2026-11-26,09:30"), encoding="utf-8")
    run(root, out, capsys=capsys)
    schedule = computed(out, "sample-2026-27", "schedule.json")
    assert schedule["all_times_pm"] is False and "All times PM" not in days_by_n(schedule)[7]["foot"]


# ------------------------------------------------------------------ standings, teams, games

def test_standings_columns_note_race_and_through(sample_out):
    standings = computed(sample_out, "sample-2026-27", "standings.json")
    assert [c["key"] for c in standings["columns"]] == ["gp", "w", "l", "t", "pts", "pf", "pa", "diff"]
    assert [c["key"] for c in standings["columns"] if c["key_col"]] == ["pts"]
    assert standings["note"] == ("2 points a win, 1 a tie and 1 for an overtime loss. "
                                 "A forfeit counts as 1–0 [placeholder].")
    assert standings["tiebreak_note"].startswith("[placeholder] The league has not decided its tiebreakers")
    assert standings["through"] == "2026-11-19" and standings["through_display"] == "Thu Nov 19"
    assert standings["race"] == {"basis": "points", "max": 10}                     # 5 games, 2 points each
    top = standings["rows"][0]
    assert top["race"] == {"pct": "80.0", "value": "8", "unit": " points", "sub": "4–1"}
    assert top["display"]["diff"] == "+11" and standings["rows"][3]["display"]["diff"] == "−5"


def test_the_archive_season_uses_its_own_points_rule(sample_out):
    standings = computed(sample_out, "sample-2025-26", "standings.json")
    assert standings["note"].startswith("3 points a win")
    assert [(r["team"], r["values"]["pts"]) for r in standings["rows"]][:2] == [("ravens", 9), ("lynx", 8)]


def test_teams_take_rank_record_and_points_from_the_standings(sample_out):
    teams = computed(sample_out, "sample-2026-27", "teams.json")
    standings = computed(sample_out, "sample-2026-27", "standings.json")
    for row in standings["rows"]:
        team = teams[row["team"]]
        assert (team["rank"], team["record"], team["points"]) == (row["rank"], row["record"], str(row["values"]["pts"]))
    assert teams["otters"]["results"] == ["2026-11-12-1", "2026-11-05-1", "2026-10-29-1", "2026-10-22-1"]
    assert teams["otters"]["upcoming"][0] == "2026-11-26-1" and "2026-11-19-1" not in teams["otters"]["upcoming"]
    assert teams["otters"]["calendar"] is None                    # sample teams have no calendar
    assert teams["otters"]["players"][:2] == ["una-w", "max-t"]


def test_tied_teams_share_a_rank(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    # A point for a win or a tie and no tiebreakers: Moose and Badgers both end on 1 and share fourth place.
    text = (root / "league.yml").read_text(encoding="utf-8")
    text += "\nstandings: {points: {win: 1, tie: 1, loss: 0, ot_win: 1, ot_loss: 0}, tiebreakers: []}\n"
    (root / "league.yml").write_text(text, encoding="utf-8")
    code, _, _ = run(root, out, capsys=capsys)
    assert code == 0
    rows = computed(out, "sample-2026-27", "standings.json")["rows"]
    assert [(r["rank"], r["team"], r["tied"]) for r in rows] == [
        (1, "ravens", False), (2, "lynx", False), (3, "otters", False), (4, "badgers", True), (4, "moose", True)]
    teams = computed(out, "sample-2026-27", "teams.json")
    assert (teams["moose"]["rank"], teams["badgers"]["rank"], teams["otters"]["rank"]) == (4, 4, 3)
    assert "Tiebreakers" not in [p["text"] for p in computed(out, "league.json")["placeholders"]]
    assert computed(out, "sample-2026-27", "standings.json")["tiebreak_note"] == (
        "Teams level on points share a rank.")


def test_games_have_results_standings_points_and_playoff_games_do_not_count(sample_out):
    games = computed(sample_out, "sample-2025-26", "games.json")
    regular = next(g for g in games.values() if g["type"] == "regular" and not g["tie"] and not g["forfeit"])
    assert regular["standings_points"]["home"] in (3, 0) and regular["standings_points"]["away"] in (3, 0)
    assert {regular["home"]["result"], regular["away"]["result"]} == {"win", "loss"}
    playoff = next(g for g in games.values() if g["type"] == "playoff")
    assert playoff["standings_points"] is None and playoff["round"] and playoff["day_label"] == playoff["round"]
    assert {playoff["home"]["result"], playoff["away"]["result"]} == {"win", "loss"}


def test_game_pages_get_final_panel_card_and_box_score(sample_out):
    game = computed(sample_out, "sample-2026-27", "games.json")["2026-11-05-1"]
    assert (game["home"]["name"], game["away"]["name"], game["tie"]) == ("Badgers", "Otters", True)
    assert game["final"] == {"status": "Final", "sub": "Tied 35–35", "note": None} and game["summary"] == "Tied 35–35"
    assert game["home"]["record_line"] == "Tie · now 0–2–1" and game["away"]["record"] == "1–1–1"
    assert game["standings_points"] == {"home": 1, "away": 1}
    assert game["line_score"]["caption"] == "Score by half" and game["card"]["meta"] == ["Court 1", "7:00 PM"]
    table = game["blocks"][0]
    assert table["type"] == "stat_table" and table["number_label"] == "#" and table["rows"][0]["num"]
    assert game["blocks"][-1]["type"] == "note"
    forfeit = computed(sample_out, "sample-2026-27", "games.json")["2026-10-22-1"]
    assert forfeit["forfeit"] == "otters" and forfeit["final"] == {
        "status": "Forfeit", "sub": "Otters forfeited",
        "note": "[placeholder] The league has not decided how a forfeit is scored yet. The site counts it as 1–0."}
    assert forfeit["line_score"] is None and forfeit["blocks"] == []
    assert (forfeit["home"]["score"], forfeit["away"]["score"]) == (1, 0)
    assert forfeit["card"]["note"] == "Otters forfeited · score [placeholder]"
    assert computed(sample_out, "sample-2026-27", "games.json")["2026-10-15-1"]["final"]["note"] is None


def test_players_and_leaders(sample_out):
    players = computed(sample_out, "sample-2026-27", "players.json")
    leaders = computed(sample_out, "sample-2026-27", "leaders.json")
    top = leaders["boards"][0]
    assert (top["id"], top["tile"], top["list"], top["first_row_in_tile"]) == ("pts", True, True, True)
    assert [(r["player"], r["value"], r["rank"]) for r in top["rows"][:3]] == [
        ("noa-a", 27, 1), ("amy-p", 24, 2), ("eve-l", 21, 3)]
    assert [r["rank"] for r in top["rows"]][5:7] == [6, 6]                      # a tie shares a rank, the next skips
    assert top["rows"][0]["detail"] == "5 GP" and top["unit"] == "PTS"
    ppg = leaders["boards"][1]
    assert ppg["min"] == {"value": 0, "placeholder": True, "note": "Minimum [placeholder] games played."}
    assert (ppg["rows"][0]["player"], ppg["rows"][0]["display"], ppg["rows"][0]["detail"]) == (
        "amy-p", "8.0", "24 pts in 3 GP")
    noa = players["noa-a"]
    assert noa["groups"]["player"]["totals"] == {"gp": 5, "pts": 27, "ppg": 5.4}
    assert noa["groups"]["player"]["ranks"] == {"pts": 1, "ppg": 5}
    assert noa["url"] == "/players/noa-a/" and [e["game"] for e in noa["log"]] == sorted(e["game"] for e in noa["log"])
    assert leaders["table"]["group"] == "player" and leaders["table"]["rows"][0] == "noa-a"
    assert leaders["table"]["columns"][1] == {"key": "pts", "label": "PTS", "title": "Points", "key_col": True}


def test_a_minimum_the_league_sets_ranks_only_players_who_reach_it(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    text = (root / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(text + "\nstats: {minimums: {ppg_min_games: 4}}\n", encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    ppg = computed(out, "sample-2026-27", "leaders.json")["boards"][1]
    assert ppg["min"] == {"value": 4, "placeholder": False, "note": "Minimum 4 games played."}
    players = computed(out, "sample-2026-27", "players.json")
    team_games = {r["team"]: r["values"]["gp"] for r in computed(out, "sample-2026-27", "standings.json")["rows"]}
    assert ppg["rows"]
    for r in ppg["rows"]:         # at least 4 games, but never more than the player's team has played (Badgers: 3)
        needed = min(4, team_games[players[r["player"]]["team"]]) if players[r["player"]]["team"] else 4
        assert players[r["player"]]["groups"]["player"]["totals"]["gp"] >= needed
    assert "amy-p" in ppg["unranked"]                                      # 3 GP, below the minimum


def test_past_seasons_have_no_team_or_player_links(sample_out):
    old_teams = computed(sample_out, "sample-2025-26", "teams.json")
    old_players = computed(sample_out, "sample-2025-26", "players.json")
    assert all(t["url"] is None for t in old_teams.values()) and all(p["url"] is None for p in old_players.values())
    assert all(g["url"].startswith("/games/") for g in computed(sample_out, "sample-2025-26", "games.json").values())


def test_playoff_totals_are_kept_apart(sample_out):
    players = computed(sample_out, "sample-2025-26", "players.json")
    with_playoffs = [p for p in players.values() if p["playoffs"]]
    assert with_playoffs
    p = with_playoffs[0]
    regular_gp = p["groups"]["player"]["totals"]["gp"] if p["groups"] else 0
    playoff_gp = p["playoffs"]["player"]["totals"]["gp"]
    assert len([e for e in p["log"] if e["type"] == "playoff"]) == playoff_gp
    assert len([e for e in p["log"] if e["type"] == "regular"]) == regular_gp


# ------------------------------------------------------------------ the archive

def test_archive_lists_the_other_shown_seasons(sample_out):
    archive = computed(sample_out, "archive.json")
    assert len(archive) == 1
    entry = archive[0]
    assert (entry["season"], entry["label"], entry["url"], entry["teams"], entry["games"]) == (
        "sample-2025-26", "2025–26", "/archive/sample-2025-26/", 5, 13)
    assert entry["standings_top"] == ["Ravens", "Lynx", "Otters"]
    assert entry["playoff_games"] == ["2025-12-04-1", "2025-12-04-2", "2025-12-11-1"]
    assert entry["sample"] is True


# ------------------------------------------------------------------ unique game ids

def test_game_ids_must_be_unique_among_the_shown_seasons(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    with (root / "data" / "sample-2025-26" / "schedule.csv").open("a", encoding="utf-8") as f:
        f.write("2026-10-15-1,2025-12-18,19:00,otters,ravens,,1,regular,,,,\n")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1 and "2026-10-15-1" in err and "must be unique" in err
    assert not out.exists()


def test_game_ids_in_computed_files_are_unique(sample_out):
    ids = [gid for sid in ("sample-2026-27", "sample-2025-26")
           for gid in computed(sample_out, sid, "games.json")]
    assert len(ids) == len(set(ids)) == 23


# ------------------------------------------------------------------ stub pages

def front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n") and text.endswith("\n---\n") and text.count("---") == 2
    return {k: json.loads(v) for k, v in (line.split(": ", 1) for line in text.split("\n")[1:-2])}


def test_stub_pages_per_collection(sample_out):
    names = lambda folder: sorted(p.stem for p in (sample_out / folder).glob("*.md"))      # noqa: E731
    games_2026 = sorted(computed(sample_out, "sample-2026-27", "games.json"))
    games_2025 = sorted(computed(sample_out, "sample-2025-26", "games.json"))
    assert names("_games") == sorted(games_2026 + games_2025)
    assert names("_archive") == ["sample-2025-26"]                       # the archive's seasons only
    assert names("_teams") == sorted(computed(sample_out, "sample-2026-27", "teams.json"))
    assert names("_players") == sorted(computed(sample_out, "sample-2026-27", "players.json"))
    assert front_matter(sample_out / "_games" / "2025-12-11-1.md")["season"] == "sample-2025-26"
    # the nav tab: a past season's game is reached from the archive; a current game keeps the collection's Schedule
    assert front_matter(sample_out / "_games" / "2025-12-11-1.md")["nav"] == "archive"
    assert "nav" not in front_matter(sample_out / "_games" / "2026-11-19-1.md")
    assert front_matter(sample_out / "_teams" / "otters.md") == {
        "season": "sample-2026-27", "team_id": "otters", "title": "Otters",
        "description": "Otters: record 1–2–1, No. 3 in the standings."}
    assert front_matter(sample_out / "_players" / "tam-k.md")["title"] == "#4 Tam K."
    assert front_matter(sample_out / "_archive" / "sample-2025-26.md")["title"] == "2025–26 season"


def test_stub_pages_are_wiped_and_rewritten_each_run(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    for folder in ("_games", "_players", "_teams", "_archive"):
        (out / folder).mkdir(parents=True)
        (out / folder / "stale.md").write_text("---\nold: 1\n---\n", encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    assert not list(out.glob("_*/stale.md"))
    assert (out / "_games" / "2026-11-19-1.md").exists()
    # a game that disappears from the data loses its page on the next run
    (root / "data" / "sample-2026-27" / "games" / "2026-11-19-1.yml").unlink()
    assert run(root, out, capsys=capsys)[0] == 0
    assert not (out / "_games" / "2026-11-19-1.md").exists() and (out / "_games" / "2026-11-12-1.md").exists()
    assert "2026-11-19-1" not in computed(out, "sample-2026-27", "games.json")


def test_drafts_are_never_built(sample_out):
    assert not (sample_out / "_games" / "2026-11-19-2.md").exists()
    assert "2026-11-19-2" not in computed(sample_out, "sample-2026-27", "games.json")


# ------------------------------------------------------------------ the atomic write

def seed_old_output(out: Path) -> dict[str, bytes]:
    (out / "_data" / "computed").mkdir(parents=True)
    (out / "_data" / "computed" / "league.json").write_text('{"old": true}\n', encoding="utf-8")
    (out / "_games").mkdir()
    (out / "_games" / "old-game.md").write_text("---\nold: 1\n---\n", encoding="utf-8")
    (out / "calendar").mkdir()
    (out / "calendar" / "old.ics").write_text("old", encoding="utf-8")
    return tree(out)


def test_nothing_is_written_when_the_data_has_a_problem(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    before = seed_old_output(out)
    game = root / "data" / "sample-2026-27" / "games" / "2026-11-12-1.yml"
    game.write_text(game.read_text(encoding="utf-8").replace("final: {home:", "final: {home: 999, x:"), encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1
    assert "data/sample-2026-27/games/2026-11-12-1.yml" in err
    assert tree(out) == before                                   # not one file added, changed or removed
    assert not (out / ".build-tmp").exists()


def test_a_problem_found_while_computing_stops_the_write_too(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    before = seed_old_output(out)
    text = (root / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(text + "\nstandings: {ties: false}\n", encoding="utf-8")     # the sample has a tie
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1 and "does not allow tied games" in err
    assert tree(out) == before


def test_a_crash_while_staging_leaves_the_old_files_alone(tmp_path, capsys, monkeypatch):
    root, out = make_repo(tmp_path), tmp_path / "out"
    before = seed_old_output(out)

    def explode(value):
        raise OSError("disk full")
    monkeypatch.setattr(writer, "dump_json", explode)
    code, _, err = run(root, out, capsys=capsys)
    assert code == 2 and "disk full" in err and "Traceback" not in err
    assert tree(out) == before


def test_a_failed_swap_puts_the_old_folders_back(tmp_path, monkeypatch):
    out = tmp_path / "out"
    seed_old_output(out)
    before = tree(out)
    real_replace = writer.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 6:                                      # fail part-way through the moves
            raise OSError("boom")
        return real_replace(src, dst)
    monkeypatch.setattr(writer.os, "replace", flaky)
    from scripts.core.compute import BuildOutput
    output = BuildOutput(data={"league.json": {"new": True}}, pages={"_games": {"new.md": {"id": "x"}}})
    with pytest.raises(OSError):
        writer.write_output(out, output)
    assert tree(out) == before and not (out / ".build-tmp").exists()


def test_the_second_run_replaces_the_first_whole(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    run(root, out, capsys=capsys)
    first = tree(out)
    assert run(root, out, capsys=capsys)[0] == 0
    assert tree(out) == first                                    # same data, same date: the same bytes


def test_json_format_is_stable(sample_out):
    text = (sample_out / "_data" / "computed" / "active.json").read_text(encoding="utf-8")
    assert text.endswith("}\n") and not text.endswith("\n\n") and '\n  "season": "sample-2026-27",\n' in text
    assert "−" in (sample_out / "_data" / "computed" / "sample-2026-27" / "standings.json").read_text(encoding="utf-8")


# ------------------------------------------------------------------ --check

def test_check_writes_nothing(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    code, stdout, err = run(root, out, "--check", capsys=capsys)
    assert code == 0 and "Nothing was written" in stdout
    assert not out.exists()
    assert "Still to decide" in err and "Tiebreakers (standings.tiebreakers)" in err


def test_check_still_finds_problems(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    (root / "data" / "sample-2026-27" / "teams.yml").write_text("- {id: otters, name: Otters}\n", encoding="utf-8")
    code, _, err = run(root, out, "--check", capsys=capsys)
    assert code == 1 and "data/sample-2026-27/teams.yml: 0.code" in err and not out.exists()


def test_check_passes_on_the_committed_data():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "--check"], cwd="/",
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "Nothing was written" in result.stdout


# ------------------------------------------------------------------ problems: exit codes, --json, annotations

def break_a_game(root: Path) -> None:
    """The Final box of one sample game no longer adds up."""
    path = root / "data" / "sample-2026-27" / "games" / "2026-11-12-2.yml"
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"(final: \{home: )\d+", r"\g<1>999", text, count=1), encoding="utf-8")


def test_exit_codes_and_the_report(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    break_a_game(root)
    code, stdout, err = run(root, out, capsys=capsys)
    assert code == 1 and stdout == ""
    assert re.search(r"^data/sample-2026-27/games/2026-11-12-2\.yml: sheet\.final\.home: the Final box says 999, "
                     r"but the halves", err, re.M)
    assert "Still to decide" in err


def test_a_bad_date_is_a_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as stop:
        build.main(["--today", "next tuesday"])
    assert stop.value.code == 2
    assert "--today must be a date" in capsys.readouterr().err


def test_json_lines(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    break_a_game(root)
    code, stdout, err = run(root, out, "--json", capsys=capsys)
    assert code == 1
    lines = [json.loads(line) for line in stdout.splitlines()]
    assert lines[0]["level"] == "error" and lines[0]["file"] == "data/sample-2026-27/games/2026-11-12-2.yml"
    assert lines[0]["at"] == "sheet.final.home" and "999" in lines[0]["message"]
    assert all(set(line) == {"level", "file", "at", "message"} for line in lines)
    assert "Still to decide" not in stdout


def test_json_keeps_stdout_clean_on_success(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    code, stdout, err = run(root, out, "--json", capsys=capsys)
    assert code == 0 and stdout == "" and "Built 2 season(s)" in err


def test_annotations(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    break_a_game(root)
    code, stdout, _ = run(root, out, "--annotations", capsys=capsys)
    assert code == 1
    assert stdout.splitlines()[0].startswith(
        "::error file=data/sample-2026-27/games/2026-11-12-2.yml,title=sheet.final.home::the Final box says 999")


def test_annotations_are_on_by_default_under_github_actions(tmp_path, capsys, monkeypatch):
    root, out = make_repo(tmp_path), tmp_path / "out"
    break_a_game(root)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    _, stdout, _ = run(root, out, capsys=capsys)
    assert "::error file=data/sample-2026-27/games/2026-11-12-2.yml" in stdout


def test_league_problems_stop_before_the_data_is_read(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    (root / "league.yml").write_text('name: "X"\nsport: curlng\ntimezone: UTC\n', encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1 and "league.yml: sport:" in err and not out.exists()


def test_a_sport_function_that_raises_is_exit_2_without_a_traceback(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    rules = root / "sports" / "stub" / "rules.py"
    rules.write_text(rules.read_text(encoding="utf-8").replace(
        "def present(reading, ctx):\n", "def present(reading, ctx):\n    raise RuntimeError('boom')\n"), encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 2
    assert "Internal error" in err and "present()" in err and "rules.py" in err and "boom" in err
    assert "Traceback" not in err and not out.exists()
    with pytest.raises(Exception, match="present"):               # --debug lets it through
        run(root, out, "--debug", capsys=capsys)


def test_a_sport_function_with_the_wrong_shape_is_exit_2(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    rules = root / "sports" / "stub" / "rules.py"
    rules.write_text(rules.read_text(encoding="utf-8").replace(
        "def derive(counts, group):\n", "def derive(counts, group):\n    return {'ppg': 'lots'}\n"), encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 2 and "derive()" in err and "wrong shape" in err


def test_a_per_period_forfeit_needs_the_sport_to_say_how_many_periods(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    sport = root / "sports" / "stub" / "sport.yml"
    sport.write_text(sport.read_text(encoding="utf-8").replace(", periods: periods}", "}"), encoding="utf-8")
    text = (root / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(text + "\nstandings: {forfeit: {score: per_period}}\n", encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 1
    assert "sports/stub/sport.yml: line_score.periods: " in err and "does not say how many periods" in err


def test_a_per_period_forfeit_scores_every_period(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    text = (root / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(text + "\nstandings: {forfeit: {score: per_period}, period_points: 1}\n",
                                     encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    game = computed(out, "sample-2026-27", "games.json")["2026-10-22-1"]
    assert (game["home"]["score"], game["away"]["score"]) == (2, 0)                  # two halves, both to the winner
    assert game["standings_points"] == {"home": 4, "away": 0}                        # 2 for the win + 1 a half


def build_with(tmp_path, capsys, extra: str):
    root, out = make_repo(tmp_path), tmp_path / "out"
    (root / "league.yml").write_text((root / "league.yml").read_text(encoding="utf-8") + "\n" + extra + "\n",
                                     encoding="utf-8")
    code, _, err = run(root, out, capsys=capsys)
    assert code == 0, err
    return out


def test_a_league_ranked_by_win_percentage(tmp_path, capsys):
    out = build_with(tmp_path, capsys, "standings: {rank_by: win_pct, columns: [gp, w, l, t, pct, gb, diff]}")
    standings = computed(out, "sample-2026-27", "standings.json")
    assert [c["key"] for c in standings["columns"] if c["key_col"]] == ["pct"]
    assert standings["race"] == {"basis": "win_pct", "max": None}
    assert standings["note"] == ("Teams are ranked by winning percentage (a tie counts as half a win). "
                                 "A forfeit counts as 1–0 [placeholder].")
    top = standings["rows"][0]
    assert top["team"] == "ravens" and top["display"]["pct"] == ".800" and top["display"]["gb"] == "—"
    assert top["race"] == {"pct": "80.0", "value": "4–1", "unit": "", "sub": "+11"}
    assert standings["rows"][1]["race"]["sub"] == "+10 · 0.5 GB"
    assert computed(out, "sample-2026-27", "teams.json")["ravens"]["points"] is None


def test_24_hour_times_and_the_scoreboard_bye(tmp_path, capsys):
    out = build_with(tmp_path, capsys, "time_format: 24h\nlayout: scoreboard")
    schedule = computed(out, "sample-2026-27", "schedule.json")
    day = days_by_n(schedule)[7]
    assert schedule["all_times_pm"] is False and day["games"][0]["time_display"] == "19:00"
    assert day["byes"] == ["moose"] and day["foot"] == ""             # the include draws "Bye: <b>Moose</b>" itself


def test_the_curling_layout_groups_a_days_games_by_start_time(tmp_path, capsys, sample_out):
    out = build_with(tmp_path, capsys, "layout: curling")
    groups = days_by_n(computed(out, "sample-2026-27", "schedule.json"))[7]["groups"]
    assert [g["time_label"] for g in groups] == ["7:00 PM", "8:15 PM"] and [len(g["games"]) for g in groups] == [1, 1]
    default = days_by_n(computed(sample_out, "sample-2026-27", "schedule.json"))[7]["groups"]
    assert len(default) == 1 and default[0]["time_label"] is None and len(default[0]["games"]) == 2


# ------------------------------------------------------------------ league.json

def test_league_json(sample_out):
    league = computed(sample_out, "league.json")
    assert league["name"] == "Example Valley Stub League" and league["tagline"] == "Stub · 2026–27"
    assert league["labels"]["results"] == "Latest results" and league["labels"]["featured"] == "Game of the week"
    assert [n["key"] for n in league["nav"]] == ["home", "schedule", "stats", "teams", "archive"]
    assert [l["url"] for l in league["footer_links"]] == ["/teams/", "/archive/", "/rules/"]
    assert league["words"]["period"] == {"one": "Half", "many": "Halves", "short": "H"}
    assert league["display"] == {"card": "rows", "card_foot": "note", "surface": "label", "card_head": ""}
    assert [p["setting"] for p in league["placeholders"]] == [
        "rules.overtime", "standings.forfeit", "standings.tiebreakers", "stats.minimums.ppg_min_games"]


def test_league_json_says_what_the_site_uses_for_each_undecided_setting(sample_out):
    using = {p["setting"]: p["using"] for p in computed(sample_out, "league.json")["placeholders"]}
    assert using == {
        "rules.overtime": "none", "standings.forfeit": "1–0", "stats.minimums.ppg_min_games": "0",
        "standings.tiebreakers": ("head-to-head record (when they have all played each other), then score difference, "
                                  "then points for")}


# ------------------------------------------------------------------ a default in use shows [placeholder]

def _forfeit_pieces(out: Path) -> tuple[str, dict, str]:
    """(the standings note, the forfeit game's final panel data, its card note) of the sample season."""
    forfeit = computed(out, "sample-2026-27", "games.json")["2026-10-22-1"]
    return computed(out, "sample-2026-27", "standings.json")["note"], forfeit["final"], forfeit["card"]["note"]


def test_a_forfeit_scored_by_the_default_is_marked_everywhere_it_shows(sample_out):
    note, final, card = _forfeit_pieces(sample_out)
    assert note.endswith("A forfeit counts as 1–0 [placeholder].")
    assert final["note"].startswith("[placeholder] The league has not decided how a forfeit is scored yet.")
    assert card == "Otters forfeited · score [placeholder]"


def test_setting_the_forfeit_score_removes_the_marker_even_when_it_is_the_default(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    text = (root / "league.yml").read_text(encoding="utf-8") + "\nstandings: {forfeit: {score: [1, 0]}}\n"
    (root / "league.yml").write_text(text, encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    note, final, card = _forfeit_pieces(out)
    assert "placeholder" not in note and final["note"] is None and card == "Otters forfeited"
    assert "standings.forfeit" not in [p["setting"] for p in computed(out, "league.json")["placeholders"]]


def test_league_settings_reach_league_json(tmp_path, capsys):
    root, out = make_repo(tmp_path), tmp_path / "out"
    text = (root / "league.yml").read_text(encoding="utf-8")
    text += ('\ncontact: league@example.org\nfooter_line: "Thursdays"\nlayout: scoreboard\ntagline: "Thursday night"\n'
             "rules: {overtime: none}\n")
    (root / "league.yml").write_text(text, encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    league = computed(out, "league.json")
    assert (league["footer_line"], league["contact_href"], league["layout"]) == ("Thursdays", "mailto:league@example.org",
                                                                                 "scoreboard")
    assert league["footer_links"][-1] == {"label": "Contact", "url": "mailto:league@example.org"}
    assert league["tagline"] == "Thursday night · 2026–27" and league["labels"]["standings"] == "The race"
    assert "rules.overtime" not in [p["setting"] for p in league["placeholders"]]


# ------------------------------------------------------------------ photos

def test_photos_are_copied_and_linked_only_when_published(tmp_path, capsys):
    root = make_repo(tmp_path)
    sheets = root / "data" / "sample-2026-27" / "sheets"
    sheets.mkdir()
    (sheets / "2026-11-12-1.jpg").write_bytes(b"jpeg bytes")
    out = tmp_path / "out"
    assert run(root, out, capsys=capsys)[0] == 0
    assert computed(out, "sample-2026-27", "games.json")["2026-11-12-1"]["photo_url"] is None
    assert not (out / "sheets").exists()
    text = (root / "league.yml").read_text(encoding="utf-8")
    (root / "league.yml").write_text(text + "\nphotos: true\n", encoding="utf-8")
    assert run(root, out, capsys=capsys)[0] == 0
    assert computed(out, "sample-2026-27", "games.json")["2026-11-12-1"]["photo_url"] == "/sheets/2026-11-12-1.jpg"
    assert (out / "sheets" / "2026-11-12-1.jpg").read_bytes() == b"jpeg bytes"
    assert computed(out, "sample-2026-27", "games.json")["2026-11-12-2"]["photo_url"] is None
    (root / "league.yml").write_text(text, encoding="utf-8")                  # photos off again: the copies go
    assert run(root, out, capsys=capsys)[0] == 0
    assert not (out / "sheets").exists()


# ------------------------------------------------------------------ the shape the includes read

# Key paths the stage 3 sample leagues (via scripts/design_system/contract.py) have and the stub's output lacks,
# each because only some sports use it. A pattern excuses that path and everything below it.
SPORT_ONLY = {
    "games.*.card.line_score": "a sport's own compact line score; the stub's cards write null and fall back to the game's",
    "games.*.line_score.columns[].blank": "curling's blank ends",
    "games.*.line_score.columns[].open": "slo-pitch's open innings",
    "games.*.line_score.legend[]": "curling and slo-pitch keys under the line score",
    "games.*.line_score.rows.home.cells[].hammer": "curling's hammer",
    "games.*.line_score.rows.away.cells[].hammer": "curling's hammer",
    "games.*.line_score.rows.home.cells[].mark": "curling's stolen ends, slo-pitch's run limit",
    "games.*.line_score.rows.away.cells[].mark": "curling's stolen ends, slo-pitch's run limit",
    "games.*.line_score.rows.home.cells[].void": "slo-pitch and curling cells not played",
    "games.*.line_score.rows.away.cells[].void": "slo-pitch and curling cells not played",
    "games.*.line_score.split[]": "hockey's goalie / PIM foot",
    "leaders.boards[].columns[]": "hockey's leaders table (a board with columns)",
    "leaders.boards[].rows[].cells.*": "hockey's leaders table",
    "games.*.blocks[].label": "basketball's top_performer block (the stub does not draw one)",
    "games.*.blocks[].player": "basketball's top_performer block",
    "games.*.blocks[].value": "basketball's top_performer block",
    "games.*.blocks[].unit": "basketball's top_performer block",
    "games.*.blocks[].detail": "basketball's top_performer block",
    "games.*.blocks[].corner": "curling's numbers block (the game in numbers)",
    "games.*.blocks[].rows[].label": "curling's numbers block",
    "games.*.blocks[].rows[].key": "curling's numbers block (the bigger value)",
    "games.*.blocks[].rows[].hot": "curling's numbers block (the stealing rink)",
    "games.*.blocks[].teams": "curling's roster block (the lineups)",
    "games.*.blocks[].link_label": "curling's roster block (the head's link)",
    "league.labels.score_sheets": "Masters-only feature (score sheet PDFs)",
    "schedule.days[].foot_link.label": "a link under the next-game panel (the Masters site's score sheet PDFs)",
    "schedule.days[].foot_link.url": "a link under the next-game panel (the Masters site's score sheet PDFs)",
}
# Same path, different basic type: the raw number sits beside the string the includes print.
TYPE_ALLOWED = {"leaders.boards[].rows[].value": "the raw value (a number); `display` is the string"}
DYNAMIC_MAPS = {"display", "values", "cells", "ranks"}
ID_KEYED_FILES = {"teams", "games", "players"}


def basic_type(v) -> str:
    if v is None:
        return "null"
    return ("bool" if isinstance(v, bool) else "num" if isinstance(v, (int, float)) else "str" if isinstance(v, str)
            else "list" if isinstance(v, list) else "dict")


def key_paths(value, prefix: str, out: dict, *, top: bool = False, file: str = "") -> None:
    """{path: {basic types}}: list items are `[]`, maps keyed by data (ids, columns) are `*`."""
    out.setdefault(prefix, set()).add(basic_type(value))
    if isinstance(value, dict):
        wildcard = (top and file in ID_KEYED_FILES) or (not top and prefix.rsplit(".", 1)[-1] in DYNAMIC_MAPS)
        for key, item in value.items():
            key_paths(item, f"{prefix}.*" if wildcard else f"{prefix}.{key}", out, file=file)
    elif isinstance(value, list):
        for item in value:
            key_paths(item, f"{prefix}[]", out, file=file)


def collect(files: dict) -> dict[str, set]:
    out: dict[str, set] = {}
    for name, value in files.items():
        if name != "case":                                   # fixture values for the test pages, never read by an include
            key_paths(value, name, out, top=True, file=name)
    return out


def covers(pattern: str, path: str) -> bool:
    return path == pattern or path.startswith((pattern + ".", pattern + "["))


def excused(path: str) -> bool:
    return any(covers(p, path) for p in SPORT_ONLY)


def test_computed_json_has_every_key_the_includes_read(sample_out):
    from scripts.design_system import contract
    wanted: dict[str, set] = {}
    for layout, sport in contract.cases():
        for path, kinds in collect(contract.build(sport, layout)).items():
            wanted.setdefault(path, set()).update(kinds)
    got: dict[str, set] = {}
    base = sample_out / "_data" / "computed"
    for name in ("league", "active"):
        key_paths(json.loads((base / f"{name}.json").read_text(encoding="utf-8")), name, got, top=True, file=name)
    for season in ("sample-2026-27", "sample-2025-26"):
        for name in ("teams", "standings", "schedule", "results", "games", "players", "leaders"):
            data = json.loads((base / season / f"{name}.json").read_text(encoding="utf-8"))
            key_paths(data, name, got, top=True, file=name)
    missing = sorted(p for p in wanted if p not in got and not excused(p))
    assert not missing, "keys the includes read that the build does not write:\n  " + "\n  ".join(missing)
    wrong = sorted(f"{p}: contract {sorted(wanted[p])}, build {sorted(got[p])}" for p in wanted if p in got
                   and p not in TYPE_ALLOWED and (wanted[p] - {"null"}) and (got[p] - {"null"})
                   and not (wanted[p] & got[p]))
    assert not wrong, "keys with a different type:\n  " + "\n  ".join(wrong)


def test_landing_json_has_every_key_the_sport_card_reads():
    """The landing page's own file (landing.json, written by scripts/landing.py; the golden file stands for it)
    against what the contract hands the sport card (contract.landing_json()). The window's teams are keyed by id."""
    from scripts.design_system import contract
    golden = json.loads((ROOT / "tests" / "golden" / "landing" / "landing.json").read_text(encoding="utf-8"))

    def paths(value) -> dict[str, set]:
        out: dict[str, set] = {}
        key_paths(value, "landing", out)
        return {re.sub(r"(window\.teams)\.[^.\[]+", r"\1.*", p): kinds for p, kinds in out.items()}
    wanted, got = paths(contract.landing_json()), paths(golden)
    # what a sport shows only when it has it: its marks (the hammer, a stolen end) and Masters' score sheet label
    sport_only = [p for p in wanted if p not in got and (p.endswith(".mark") or p.endswith("labels.score_sheets"))]
    missing = sorted(p for p in wanted if p not in got and p not in sport_only)
    assert not missing, "keys the sport card reads that landing.json does not have:\n  " + "\n  ".join(missing)
    wrong = sorted(p for p in wanted if p in got and (wanted[p] - {"null"}) and (got[p] - {"null"}) and not wanted[p] & got[p])
    assert not wrong, "keys with a different type:\n  " + "\n  ".join(wrong)


def test_every_excused_key_is_really_missing(sample_out):
    """The list of exceptions must not go stale: each entry still names something the stub does not write."""
    from scripts.design_system import contract
    wanted: dict[str, set] = {}
    for layout, sport in contract.cases():
        wanted.update(collect(contract.build(sport, layout)))
    for pattern in SPORT_ONLY:
        assert any(covers(pattern, p) for p in wanted), f"{pattern} is not in the contract"
        assert pattern not in got_by_stub(sample_out), f"{pattern} is now written by the build: drop it from SPORT_ONLY"


def got_by_stub(sample_out: Path) -> set[str]:
    """The key paths the stub's build writes with a value (a path that is only ever null counts as not written)."""
    got: dict[str, set] = {}
    base = sample_out / "_data" / "computed"
    for name in ("league", "active"):
        key_paths(json.loads((base / f"{name}.json").read_text(encoding="utf-8")), name, got, top=True, file=name)
    for season in ("sample-2026-27", "sample-2025-26"):
        for name in ("teams", "standings", "schedule", "results", "games", "players", "leaders"):
            data = json.loads((base / season / f"{name}.json").read_text(encoding="utf-8"))
            key_paths(data, name, got, top=True, file=name)
    return {path for path, kinds in got.items() if kinds != {"null"}}


def test_a_spare_with_no_team_has_one_full_stop_in_the_page_description(sample_out):
    """'Season totals and game log for Pax F.' and not '...Pax F..' (the name already ends in a full stop)."""
    players = computed(sample_out, "sample-2026-27", "players.json")
    spares = [p for p in players.values() if p["team"] is None]
    assert spares, "the sample season should have a spare with no team"
    for p in spares:
        text = (sample_out / "_players" / f"{p['id']}.md").read_text(encoding="utf-8")
        assert f'for {p["name"]}"' in text and '.."' not in text


# ------------------------------------------------------------------ core extensions E2-E4 (stage 5 spec, section 5)

def mini_season(tmp_path: Path, *, sport_edit=None, rules_edit=(), playoff=False, games=None) -> Path:
    """A real (not sample) season of two teams, four players and four games, built on a copy of the stub sport.
    `sport_edit(spec)` changes the parsed sport.yml; `rules_edit` is [(old, new)] text replacements in rules.py.
    Ann plays three games for 61 points, Bob four for 81 (20.33 and 20.25 points per game), Dee scores 0 once.
    With `playoff` a playoff game is added, won by the reds, with Ann on 30. `games` replaces the four games."""
    import yaml
    root = make_repo(tmp_path, sample_data=False)
    # The stub sport and only the real season, whatever sport and sample seasons the repo's league uses.
    league = root / "league.yml"
    league.write_text(re.sub(r"(?m)^sport: .*$", "sport: stub", league.read_text(encoding="utf-8")), encoding="utf-8")
    (root / "data" / "seasons.yml").write_text('- {id: 2026-27, label: "2026–27", current: true, venue: Gym}\n',
                                                encoding="utf-8")
    for sample in (root / "data").glob("sample-*"):
        shutil.rmtree(sample)
    season = root / "data" / "2026-27"
    (season / "teams.yml").write_text("- {id: reds, name: Reds, code: RED}\n- {id: blues, name: Blues, code: BLU}\n",
                                      encoding="utf-8")
    (season / "players.yml").write_text(
        "- {id: ann-r, name: Ann R., team: reds, number: 7}\n- {id: bob-r, name: Bob R., team: reds, number: 8}\n"
        "- {id: cal-b, name: Cal B., team: blues, number: 9}\n- {id: dee-b, name: Dee B., team: blues, number: 10}\n",
        encoding="utf-8")
    games = games or [  # (date, reds' points by player, blues' points by player, kind)
        ("2026-10-15", {"ann-r": 20, "bob-r": 20}, {"cal-b": 15, "dee-b": 0}, "regular"),
        ("2026-10-22", {"ann-r": 20, "bob-r": 20}, {"cal-b": 15}, "regular"),
        ("2026-10-29", {"ann-r": 21, "bob-r": 20}, {"cal-b": 15}, "regular"),
        ("2026-11-05", {"bob-r": 21}, {"cal-b": 15}, "regular"),
    ]
    if playoff:
        games.append(("2027-01-07", {"ann-r": 30, "bob-r": 5}, {"cal-b": 10, "dee-b": 3}, "playoff"))
    rows = ["game_id,date,time,home,away,venue,surface,type,round,week,status,moved_from"]
    for date, reds, blues, kind in games:
        gid = f"{date}-1"
        rows.append(f"{gid},{date},19:00,reds,blues,,1,{kind},{'Final' if kind == 'playoff' else ''},,,")
        home, away = sum(reds.values()), sum(blues.values())
        players = lambda side: "".join(f"      - {{player: {p}, pts: {n}}}\n" for p, n in side.items())
        (season / "games" / f"{gid}.yml").write_text(
            f"game_id: {gid}\nstatus: final\nhome: reds\naway: blues\nchecked_by: Pat S.\nscorekeeper: Sam T.\nsheet:\n  periods: {{home: [{home - 1}, 1], away: [{away - 1}, 1]}}\n"
            f"  final: {{home: {home}, away: {away}}}\n  players:\n    home:\n{players(reds)}    away:\n{players(blues)}",
            encoding="utf-8")
    (season / "schedule.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    sport_yml = root / "sports" / "stub" / "sport.yml"
    spec = yaml.safe_load(sport_yml.read_text(encoding="utf-8"))
    if sport_edit:
        sport_edit(spec)
        sport_yml.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rules = root / "sports" / "stub" / "rules.py"
    text = rules.read_text(encoding="utf-8")
    for old, new in rules_edit:
        assert old in text, old
        text = text.replace(old, new)
    rules.write_text(text, encoding="utf-8")
    return root


def build_mini(tmp_path, capsys, **kwargs):
    root, out = mini_season(tmp_path, **kwargs), tmp_path / "out"
    code, _, err = run(root, out, capsys=capsys, today="2027-03-01")
    assert code == 0, err
    return computed(out, "2026-27", "leaders.json"), computed(out, "2026-27", "players.json"), out


UNROUNDED_PPG = [('return {"ppg": float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))}', 'return {"ppg": float(value)}')]


def test_rates_are_ranked_before_they_are_rounded(tmp_path, capsys):
    """E2: Ann averages 20.33 and Bob 20.25, both shown as 20.3 (one decimal, half up); Ann is still ahead."""
    leaders, players, _ = build_mini(tmp_path, capsys, rules_edit=UNROUNDED_PPG)
    ppg = next(b for b in leaders["boards"] if b["id"] == "ppg")
    assert [(r["player"], r["display"], r["value"], r["rank"]) for r in ppg["rows"][:2]] == [
        ("ann-r", "20.3", 20.3, 1), ("bob-r", "20.3", 20.3, 2)]
    assert players["ann-r"]["groups"]["player"]["ranks"]["ppg"] == 1 and players["bob-r"]["groups"]["player"]["ranks"]["ppg"] == 2
    assert players["ann-r"]["groups"]["player"]["totals"]["ppg"] == 20.3 and "exact" not in players["ann-r"]["groups"]["player"]


def test_rates_that_show_the_same_whole_number_still_rank_apart(tmp_path, capsys):
    leaders, _, _ = build_mini(tmp_path, capsys, rules_edit=UNROUNDED_PPG, sport_edit=lambda s: s["stats"]["derived"][0].update(places=0))
    ppg = next(b for b in leaders["boards"] if b["id"] == "ppg")
    assert [(r["player"], r["display"], r["rank"]) for r in ppg["rows"][:2]] == [("ann-r", "20", 1), ("bob-r", "20", 2)]


# Ann and Cal both average 61 / 3 (20.33), Bob 81 / 4 (20.25): all three show 20.3.
EQUAL_EXACT = [("2026-10-15", {"ann-r": 20, "bob-r": 20}, {"cal-b": 20, "dee-b": 0}, "regular"),
               ("2026-10-22", {"ann-r": 20, "bob-r": 20}, {"cal-b": 20}, "regular"),
               ("2026-10-29", {"ann-r": 21, "bob-r": 20}, {"cal-b": 21}, "regular"),
               ("2026-11-05", {"bob-r": 21}, {"dee-b": 15}, "regular")]


def test_rates_that_are_exactly_equal_share_a_rank(tmp_path, capsys):
    leaders, players, _ = build_mini(tmp_path, capsys, rules_edit=UNROUNDED_PPG, games=EQUAL_EXACT)
    ppg = next(b for b in leaders["boards"] if b["id"] == "ppg")
    assert [(r["player"], r["display"], r["rank"]) for r in ppg["rows"][:3]] == [
        ("ann-r", "20.3", 1), ("cal-b", "20.3", 1), ("bob-r", "20.3", 3)]
    assert players["cal-b"]["groups"]["player"]["ranks"]["ppg"] == 1


def test_the_stats_table_sorts_a_rate_on_its_exact_value(tmp_path, capsys):
    """Shown alike (20.3), Ann and Cal (20.33) still come before Bob (20.25), as on the board, not by name."""
    def spec_edit(spec):
        spec["stats"]["columns"] = {"player": {"table": ["gp", "ppg"]}}           # PPG is the key column
    leaders, _, _ = build_mini(tmp_path, capsys, rules_edit=UNROUNDED_PPG, games=EQUAL_EXACT, sport_edit=spec_edit)
    assert [c["key"] for c in leaders["table"]["columns"] if c["key_col"]] == ["ppg"]
    assert leaders["table"]["rows"] == ["ann-r", "cal-b", "bob-r", "dee-b"]


def test_a_sport_that_rounds_in_derive_ranks_as_before(tmp_path, capsys):
    leaders, _, _ = build_mini(tmp_path, capsys)                      # the stub rounds to 20.3 and 20.3 itself
    ppg = next(b for b in leaders["boards"] if b["id"] == "ppg")
    assert [(r["player"], r["rank"]) for r in ppg["rows"][:2]] == [("ann-r", 1), ("bob-r", 1)]


@pytest.mark.parametrize("ann, bob", [("{name: Terry N., number: 38}", "{name: Mark D., number: 5}"),
                                      ("{name: Sam R., number: 38}", "{name: Sam R., number: 5}")])
def test_equal_values_are_listed_by_name_then_by_number_as_a_number(tmp_path, ann, bob):
    """Ann and Bob tie at 20.3 (the stub rounds in derive). '#38 Terry N.' sorts before '#5 Mark D.' as text;
    the board lists Mark first (by name), and of two 'Sam R.' #5 before #38."""
    root = mini_season(tmp_path)
    players = root / "data" / "2026-27" / "players.yml"
    text = players.read_text(encoding="utf-8")
    text = text.replace("{id: ann-r, name: Ann R., team: reds, number: 7}", "{id: ann-r, team: reds, " + ann[1:])
    text = text.replace("{id: bob-r, name: Bob R., team: reds, number: 8}", "{id: bob-r, team: reds, " + bob[1:])
    players.write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    assert build.main(["--root", str(root), "--out", str(out), "--today", "2027-03-01"]) == 0
    ppg = next(b for b in computed(out, "2026-27", "leaders.json")["boards"] if b["id"] == "ppg")
    assert [(r["player"], r["rank"]) for r in ppg["rows"][:2]] == [("bob-r", 1), ("ann-r", 1)]


def add_boards(spec):
    """Boards on the same two stats as the stub's, each with one switch, after the stub's own."""
    spec["leaderboards"] += [
        {"id": "ppg_zero", "of": "player", "group": "player", "stat": "ppg", "label": "PPG with zeros", "zero": True,
         "player_rank": False},
        {"id": "pts_all", "of": "player", "group": "player", "stat": "pts", "label": "Points with playoffs",
         "playoffs": True, "home": False, "player_rank": False, "detail": "{gp} GP"},
        {"id": "pts_plain", "of": "player", "group": "player", "stat": "pts", "label": "Points only", "home": False}]


def test_a_zero_is_ranked_only_on_a_board_with_zero_true(tmp_path, capsys):
    leaders, _, _ = build_mini(tmp_path, capsys, sport_edit=add_boards)
    by_id = {b["id"]: b for b in leaders["boards"]}
    assert "dee-b" not in [r["player"] for r in by_id["ppg"]["rows"]]
    rows = by_id["ppg_zero"]["rows"]
    assert (rows[-1]["player"], rows[-1]["display"], rows[-1]["rank"]) == ("dee-b", "0.0", 4)


def test_playoffs_true_counts_playoff_games_and_the_other_boards_do_not(tmp_path, capsys):
    leaders, players, _ = build_mini(tmp_path, capsys, sport_edit=add_boards, playoff=True)
    by_id = {b["id"]: b for b in leaders["boards"]}
    assert [(r["player"], r["value"]) for r in by_id["pts"]["rows"][:2]] == [("bob-r", 81), ("ann-r", 61)]
    assert [(r["player"], r["value"], r["detail"]) for r in by_id["pts_all"]["rows"][:2]] == [
        ("ann-r", 91, "4 GP"), ("bob-r", 86, "5 GP")]                    # 61 + 30 and 81 + 5; GP counts the playoff game
    assert players["ann-r"]["groups"]["player"]["totals"]["pts"] == 61  # the player's season row stays regular season
    assert players["ann-r"]["playoffs"]["player"]["totals"]["pts"] == 30


def test_a_board_for_playoff_games_counts_a_player_with_only_playoff_games(tmp_path, capsys):
    root = mini_season(tmp_path, sport_edit=add_boards, playoff=True)
    season = root / "data" / "2026-27"
    # Dee's only regular-season game goes to Cal, so her only points come in the playoff game.
    first = season / "games" / "2026-10-15-1.yml"
    first.write_text(first.read_text(encoding="utf-8").replace("      - {player: dee-b, pts: 0}\n", ""), encoding="utf-8")
    out = tmp_path / "out"
    assert build.main(["--root", str(root), "--out", str(out), "--today", "2027-03-01"]) == 0
    board = next(b for b in computed(out, "2026-27", "leaders.json")["boards"] if b["id"] == "pts_all")
    assert ("dee-b", 3) in [(r["player"], r["value"]) for r in board["rows"]]


def test_home_and_player_rank_switches_reach_the_board_and_the_ranks_line(tmp_path, capsys):
    leaders, players, _ = build_mini(tmp_path, capsys, sport_edit=add_boards, playoff=True)
    flags = {b["id"]: (b["home"], b["player_rank"]) for b in leaders["boards"]}
    assert flags == {"pts": (True, True), "ppg": (True, True), "ppg_zero": (True, False), "pts_all": (False, False),
                     "pts_plain": (False, True)}
    ranks = players["ann-r"]["groups"]["player"]["ranks"]
    assert ranks == {"pts": 2, "ppg": 1}          # pts_all and ppg_zero are left out; the first board on a stat gives its rank


def test_column_lists_set_the_order_of_each_table(tmp_path, capsys):
    def spec_edit(spec):
        spec["stats"]["columns"] = {"player": {"table": ["ppg", "pts"], "totals": ["pts", "gp"], "log": ["pts"]}}
    leaders, _, _ = build_mini(tmp_path, capsys, sport_edit=spec_edit)
    cols = leaders["columns"]["player"]
    shape = {name: [(c["key"], c["key_col"]) for c in cols[name]] for name in ("table", "totals", "log")}
    assert shape == {"table": [("ppg", False), ("pts", True)],           # the key column is the first board's stat
                     "totals": [("pts", True), ("gp", False)], "log": [("pts", True)]}
    assert leaders["table"]["columns"] == cols["table"]                  # the Stats table sorts on its key column


def test_column_lists_left_out_keep_the_default_order(tmp_path, capsys):
    def spec_edit(spec):
        spec["stats"]["columns"] = {"player": {"table": ["pts", "gp"]}}
    leaders, _, _ = build_mini(tmp_path, capsys, sport_edit=spec_edit)
    cols = leaders["columns"]["player"]
    assert [c["key"] for c in cols["table"]] == ["pts", "gp"]
    assert [c["key"] for c in cols["totals"]] == [c["key"] for c in cols["log"]] == ["gp", "pts", "ppg"]


# ------------------------------------------------------------------ core extensions E7-E10 (curling spec, section 6)

COMPACT_CARD = [(
    '    return {"line_score": line_score, "card": card, "tiles": [], "blocks": blocks}',
    '    card = {**card, "line_score": {**line_score, "title": "Compact", "legend": []}, "meta_extra": ["Shook hands after 6"]}\n'
    '    return {"line_score": line_score, "card": card, "tiles": [], "blocks": blocks}')]

OVERTIME_GAME = ("game_id: 2026-10-15-1\nstatus: final\nhome: reds\naway: blues\nchecked_by: Pat S.\nscorekeeper: Sam T.\n"
                 "sheet:\n  periods: {home: [10, 10], away: [10, 10]}\n  overtime: {home: 3, away: 1}\n"
                 "  final: {home: 23, away: 21}\n  players:\n    home:\n      - {player: ann-r, pts: 20}\n      - {player: bob-r, pts: 3}\n"
                 "    away:\n      - {player: cal-b, pts: 15}\n      - {player: dee-b, pts: 6}\n")


def extension_build(tmp_path, capsys, *, edit=None, rules_edit=(), league_yml="", position_players=False):
    """The mini season (stub sport) with the first game decided in overtime, `edit(spec)` applied to sport.yml and
    `league_yml` appended to league.yml. Returns the output folder."""
    root = mini_season(tmp_path, sport_edit=edit, rules_edit=rules_edit)
    season = root / "data" / "2026-27"
    (season / "games" / "2026-10-15-1.yml").write_text(OVERTIME_GAME, encoding="utf-8")
    league = root / "league.yml"
    league.write_text(league.read_text(encoding="utf-8") + "\nrules: {overtime: overtime}\n" + league_yml, encoding="utf-8")
    if position_players:
        (season / "players.yml").write_text(
            "- {id: ann-r, name: Ann R., team: reds, position: skip}\n- {id: bob-r, name: Bob R., team: reds, position: skip}\n"
            "- {id: cal-b, name: Cal B., team: blues, position: lead}\n"
            "- {id: dee-b, name: Dee B., team: blues, position: skip, sub: true}\n", encoding="utf-8")
    out = tmp_path / "out"
    code, _, err = run(root, out, capsys=capsys, today="2027-03-01")
    assert code == 0, err
    return out


def test_e7_a_card_may_carry_its_own_line_score_and_extra_meta(tmp_path, capsys):
    out = extension_build(tmp_path, capsys, rules_edit=COMPACT_CARD)
    game = computed(out, "2026-27", "games.json")["2026-10-22-1"]
    card = game["card"]
    assert card["meta"] == ["Court 1", "7:00 PM", "Shook hands after 6"]          # the sheet and time, then meta_extra
    compact = card["line_score"]
    assert compact["title"] == "Compact" and compact["rows"] == game["line_score"]["rows"]
    # the line score's defaults are filled in as for the game's own
    assert compact["caption"] == "Score by half" and compact["void_word"] == "not played" and compact["note"] is None
    assert compact["rows"]["home"]["extra"] is None and compact["rows"]["home"]["hammer_first"] is False
    assert game["line_score"]["title"] is None                                  # the page's line score is its own copy


def test_e7_without_them_a_card_has_a_null_line_score_and_only_the_sheet_and_time(sample_out):
    games = computed(sample_out, "sample-2026-27", "games.json")
    assert all(g["card"]["line_score"] is None for g in games.values())        # also the forfeit's card
    assert games["2026-11-05-1"]["card"]["meta"] == ["Court 1", "7:00 PM"]
    assert games["2026-10-22-1"]["forfeit"] and games["2026-10-22-1"]["card"]["line_score"] is None


def test_e8_the_extra_word_names_the_final_status_the_points_and_the_tiebreak(tmp_path, capsys):
    def edit(spec):
        spec["words"]["period"] = {"one": "End", "many": "Ends", "short": "E"}
        spec["words"]["extra"] = {"one": "Extra end", "short": "EE"}
    out = extension_build(tmp_path, capsys, edit=edit, league_yml=(
        "standings: {points: {win: 2, tie: 1, loss: 0, ot_win: 3, ot_loss: 1}, tiebreakers: [head_to_head, periods_won]}\n"))
    games = computed(out, "2026-27", "games.json")
    assert games["2026-10-15-1"]["final"]["status"] == "Final · EE" and games["2026-10-15-1"]["status"] == "Final · EE"
    assert games["2026-10-22-1"]["final"]["status"] == "Final"
    standings = computed(out, "2026-27", "standings.json")
    assert "3 for an extra-end win and 1 for an extra-end loss" in standings["note"]
    assert "overtime" not in standings["note"]
    assert "ranked by head-to-head record (when they have all played each other), then ends won;" in standings["tiebreak_note"]


def test_e8_without_an_extra_word_the_core_still_says_overtime(tmp_path, capsys):
    out = extension_build(tmp_path, capsys, league_yml=(
        "standings: {points: {win: 2, tie: 1, loss: 0, ot_win: 3, ot_loss: 1}, tiebreakers: [periods_won]}\n"))
    games = computed(out, "2026-27", "games.json")
    assert games["2026-10-15-1"]["final"]["status"] == "Final · OT"
    standings = computed(out, "2026-27", "standings.json")
    assert "3 for an overtime win and 1 for an overtime loss" in standings["note"]
    assert "then" not in standings["tiebreak_note"] and "halves won" in standings["tiebreak_note"]


def test_e8_the_extra_word_is_also_the_default_in_use_for_the_tiebreakers(tmp_path, capsys):
    """The [placeholder] list says what the site uses for tiebreakers the league has not decided."""
    def edit(spec):
        spec["words"]["period"] = {"one": "End", "many": "Ends", "short": "E"}
        spec["standings"]["tiebreakers"] = {"value": ["periods_won"], "decide": True}
    out = extension_build(tmp_path, capsys, edit=edit)
    using = {p["setting"]: p["using"] for p in computed(out, "league.json")["placeholders"]}
    assert using["standings.tiebreakers"] == "ends won"


def test_e9_the_results_legend_reaches_league_json(tmp_path, capsys, sample_out):
    legend = [{"kind": "hammer", "text": "Hammer in end 1"}, {"kind": "mark", "text": "Stolen end"}]
    out = extension_build(tmp_path, capsys, edit=lambda spec: spec["display"].update(results_legend=legend))
    league = computed(out, "league.json")
    assert league["results_legend"] == legend and "results_legend" not in league["display"]
    assert league["display"]["card"] == "rows"                                  # the rest of display is as it was
    assert computed(sample_out, "league.json")["results_legend"] == []          # a sport without one: an empty list


def test_e10_the_team_card_names_the_regular_in_the_team_sub_position(tmp_path, capsys, sample_out):
    def edit(spec):
        spec["positions"] = ["lead", "skip"]
        spec["display"]["team_sub"] = "skip"
    out = extension_build(tmp_path, capsys, edit=edit, position_players=True)
    teams = computed(out, "2026-27", "teams.json")
    assert teams["reds"]["sub"] == "Skip Ann R."                                # two skips: the first in players.yml
    assert teams["blues"]["sub"] is None                                        # its only skip is a spare
    assert all(t["sub"] is None for t in computed(sample_out, "sample-2026-27", "teams.json").values())


def test_e10_a_sport_without_team_sub_leaves_the_line_empty(tmp_path, capsys):
    def edit(spec):
        spec["positions"] = ["lead", "skip"]
    out = extension_build(tmp_path, capsys, edit=edit, position_players=True)
    assert all(t["sub"] is None for t in computed(out, "2026-27", "teams.json").values())


def test_e8_the_game_log_says_the_extra_word_from_the_computed_json(tmp_path, capsys):
    """A player's game log reads its result from `result_label`: "Win (OT)" by default, the sport's
    `words.extra.short` when it has one ("Loss (EE)"), so no include says OT on a curling page."""
    def log_labels(out):
        players = computed(out, "2026-27", "players.json")
        return {pid: {e["game"]: e["result_label"] for e in players[pid]["log"]} for pid in ("ann-r", "cal-b")}
    (tmp_path / "plain").mkdir()
    (tmp_path / "extra").mkdir()
    plain = log_labels(extension_build(tmp_path / "plain", capsys))
    assert plain["ann-r"]["2026-10-15-1"] == "Win (OT)" and plain["cal-b"]["2026-10-15-1"] == "Loss (OT)"
    assert set(plain["ann-r"].values()) - {"Win (OT)", "Loss (OT)"} <= {"Win", "Loss", "Tie"}

    def edit(spec):
        spec["words"]["extra"] = {"one": "Extra end", "short": "EE"}
    curl = log_labels(extension_build(tmp_path / "extra", capsys, edit=edit))
    assert curl["ann-r"]["2026-10-15-1"] == "Win (EE)" and curl["cal-b"]["2026-10-15-1"] == "Loss (EE)"


def test_e7_a_card_meta_extra_that_is_not_a_list_of_strings_is_a_sport_bug():
    from scripts.core.problems import InternalError, call_sport

    def present(card):
        return lambda: {"line_score": None, "card": card, "tiles": [], "blocks": []}
    assert call_sport("present", present({"meta_extra": ["Shook hands after 6"]}))["card"]["meta_extra"]
    for bad in ("Shook hands after 6", [6]):
        with pytest.raises(InternalError, match=r"meta_extra'\] must be a list of strings"):
            call_sport("present", present({"meta_extra": bad}))
