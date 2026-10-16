"""The Masters converter (sports/basketball/convert_masters.py, docs/stage-5-basketball-spec.md sections 2.2 and
2.4), offline: small Masters-shaped files are written inside each test, so this runs in CI and refers to nothing
outside the repository. The comparison with the real Masters site is tests/test_masters_parity.py (local only).

What is covered: every key mapping of 2.2, the review paths, forfeit notes left out and printed, the Masters
preset it prints, photos only with --photos, and refusing a folder that already has files.
"""
import csv
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "sports" / "basketball" / "convert_masters.py"

_spec = importlib.util.spec_from_file_location("convert_masters", SCRIPT)
convert_masters = importlib.util.module_from_spec(_spec)
sys.modules["convert_masters"] = convert_masters
_spec.loader.exec_module(convert_masters)

# --------------------------------------------------------------------------- Masters-shaped input

SEASONS = """\
# Seasons, newest first.
- id: 2026-27
  label: "2026-27"
  current: true
  gym: "St. Pat's"
  gym_address: "1 Main St, Anytown, ON A1A 1A1"
  ppg_min_games: 3
  ft_min_attempts: 10

- id: sample-2026-27
  label: "2026-27"
  sample: true
  stands_in_for: 2026-27
  gym: "St. Pat's"

- id: sample-2025-26
  label: "2025-26"
  sample: true
  gym: "Old Gym"
  ppg_min_games: 0
"""

TEAMS = """\
# colour_slot picks --mb-team-N; the hex values are a record only.
- id: aa
  name: Alpha
  short: AL
  colour_slot: 1
  colour_light: "#C8102E"
  colour_dark: "#E8394F"
- id: bb
  name: "Bravo"
  short: BR
  colour_slot: 2
  colour_light: "#1F6FB5"
  colour_dark: "#4D8FE0"
"""

PLAYERS = """\
- {id: al-a, display: Al A., team: aa, sub: false, number: 4}
- {id: amy-b, display: Amy B., team: aa, sub: false, number: 10}
- {id: ann-c, display: Ann C., team: aa, sub: false, number: 22}
- {id: ari-d, display: Ari D., team: aa, sub: false, number: 7}
- {id: abe-z, display: Abe Z., team: aa, sub: false, number: "00"}
- {id: bo-c, display: Bo C., team: bb, sub: false, number: 5}
- {id: bev-d, display: Bev D., team: bb, sub: false, number: 11}
- {id: bud-e, display: Bud E., team: bb, sub: false, number: 30}
- {id: sam-s, display: Sam S., team: bb, sub: true}
"""

SCHEDULE = """\
game_id,date,time,gym,home,away,type,week,status,round
2026-10-17-g1,2026-10-17,09:45,,aa,bb,regular,1,,
2026-10-24-g1,2026-10-24,11:15,Annex,bb,aa,regular,2,,
2026-11-21-g1,2026-11-21,09:45,,aa,bb,regular,2,cancelled,
2026-10-31-g1,2026-10-31,09:45,,aa,bb,regular,3,,
2026-11-07-g1,2026-11-07,09:45,,aa,bb,regular,4,,
2026-11-14-g1,2026-11-14,09:45,,aa,bb,regular,5,,
2026-11-28-g1,2026-11-28,09:45,,aa,bb,playoff,6,,"Semifinal, G1"
2026-12-05-g1,2026-12-05,09:45,,1st,Winner G41,playoff,7,,Final
"""

CLEAN = """\
# A clean game. aa 22, bb 19. Ari D. (#7) is on the sheet but didn't play.
game_id: 2026-10-17-g1
form: MBL-SS6
status: final
home: aa
away: bb
scorekeeper: Pat S.
teams:
  aa:
    players:
      - {player: al-a, num: 4, here: true, ft: MXM, fouls: 2}
      - {player: amy-b, num: 10, here: true, ft: X}
      - {player: ann-c, num: 22, here: true, ft: M, fouls: 1}
      - {player: ari-d, num: 7, here: false}
  bb:
    players:
      - {player: bo-c, num: 5, here: true, ft: M, fouls: 3, tech: 1}
      - {player: bev-d, num: 11, here: true, ft: XM}
      - {player: bud-e, num: 30, here: true, ft: MX}
running:
  aa: {2: 4, 4: 10, 5: 4, 7: 22, 10: 4, 12: 10, 13: 22, 15: 4, 17: 22, 19: 10, 20: 4, 22: 22}
  bb: {3: 5, 5: 11, 6: 30, 8: 5, 10: 11, 11: 5, 14: 30, 16: 11, 17: 11, 19: 5}
lines:
  aa: [5, 12, 17, 22]
  bb: [5, 10, 16, 19]
boxes:
  aa: {q1: 5, q2: 12, q3: 17, q4: 22, ot: null, final: 22}
  bb: {q1: 5, q2: 10, q3: 16, q4: 19, ot: null, final: 19}
checked_by: Lee M.
"""

# The home side is bb here, so a side's key is not the team id's position in the file.
FLAGRANT = """\
game_id: 2026-10-24-g1
form: MBL-SS6
status: final
home: bb
away: aa
teams:
  bb:
    players:
      - {player: bo-c, num: 5, here: true, ft: M, fouls: 3, tech: 1}
      - {player: bud-e, num: 30, here: true}
  aa:
    players:
      - {player: abe-z, num: "00", here: true, ft: MX, fouls: 2}
      - {player: al-a, num: 4, here: true}
running:
  bb: {2: 5, 3: 30}
  aa: {1: "00", 3: 4}
lines:
  bb: [3, 3, 3, 3]
  aa: [3, 3, 3, 3]
boxes:
  bb: {q1: 3, q2: 3, q3: 3, q4: 3, ot: null, final: 3}
  aa: {q1: 3, q2: 3, q3: 3, q4: 3, ot: null, final: 3}
notes:
  - {team: aa, num: "00", q: 3, kind: flagrant, text: "elbow on a rebound: no foul called"}
  - {team: bb, num: 5, q: OT, kind: note, text: "bench warned, twice"}
  - {team: zz, num: 5, q: 1, kind: flagrant, text: a team that is not in the game}
checked_by: Lee M.
"""

DRAFT = """\
# Jim K. (#31) subbed for bb and was written in by hand.
game_id: 2026-10-31-g1
form: MBL-SS6
status: draft
home: aa
away: bb
scorekeeper: Pat S.
teams:
  aa:
    players:
      - {player: al-a, num: 4, here: true, ft: MXM, fouls: 2}
  bb:
    players:
      - {player: bo-c, num: 5, here: true}
      - {num: 31, name: Jim K., here: true}
running:
  aa: {2: 4}
  bb: {3: 5, 6: 31}
lines:
  bb: [3, 6, 6, 6]
boxes:
  aa: {q1: 2, q2: null, q3: null, q4: null, ot: null, final: 4}
  bb: {q1: 3, q2: 6, q3: 6, q4: 6, ot: null, final: 6}
review:
  - {at: running.bb.6, note: "31 or 37?"}
  - {at: teams.bb.players.1, note: "who is #31?"}
  - {at: teams.bb.players.0.ft.2, note: "circle 3"}
  - {at: lines.aa, note: "no line drawn"}
  - {at: lines.bb.1, note: "Q2 line"}
  - {at: boxes.aa.final, note: "4 or 9?"}
  - {at: notes.0, note: "flagrant?"}
  - {at: notes.0.team, note: "which team?"}
  - {at: checked_by, note: "not checked yet"}
  - {at: form, note: "wrong form?"}
"""

FORFEIT = """\
# bb couldn't field four players: a forfeit. No score sheet, only who forfeited.
game_id: 2026-11-14-g1
form: MBL-SS6
status: final
home: aa
away: bb
forfeit: bb
notes:
  - {kind: note, text: bb had three players at 9:55}
  - {kind: note, text: "aa agreed to play a friendly"}
checked_by: Lee M.
"""

FORFEIT_DRAFT = """\
game_id: 2026-11-07-g1
form: MBL-SS6
status: draft
home: aa
away: bb
forfeit: aa
review:
  - {at: forfeit, note: "who forfeited?"}
  - {at: notes.0, note: "keep this note?"}
notes:
  - {kind: note, text: "no show"}
"""


def masters_folder(root: Path, *, photos: bool = True) -> Path:
    """A small Masters data/ folder: three seasons, the first with games, a draft, a forfeit and photos."""
    data = root / "masters-data"
    (data / "2026-27").mkdir(parents=True)
    (data / "seasons.yml").write_text(SEASONS, encoding="utf-8")
    for season in ("2026-27", "sample-2026-27", "sample-2025-26"):
        folder = data / season
        (folder / "games").mkdir(parents=True, exist_ok=True)
        (folder / "drafts").mkdir(exist_ok=True)
        (folder / "sheets").mkdir(exist_ok=True)
        (folder / "teams.yml").write_text(TEAMS, encoding="utf-8")
        (folder / "players.yml").write_text(PLAYERS if season == "2026-27" else "[]\n", encoding="utf-8")
        (folder / "schedule.csv").write_text(SCHEDULE, encoding="utf-8")
        (folder / "sheets" / ".gitkeep").write_text("", encoding="utf-8")
    season = data / "2026-27"
    (season / "games" / "2026-10-17-g1.yml").write_text(CLEAN, encoding="utf-8")
    (season / "games" / "2026-10-24-g1.yml").write_text(FLAGRANT, encoding="utf-8")
    (season / "games" / "2026-11-14-g1.yml").write_text(FORFEIT, encoding="utf-8")
    (season / "drafts" / "2026-10-31-g1.yml").write_text(DRAFT, encoding="utf-8")
    (season / "drafts" / "2026-11-07-g1.yml").write_text(FORFEIT_DRAFT, encoding="utf-8")
    if photos:
        (season / "sheets" / "2026-10-17-g1.jpg").write_bytes(b"\xff\xd8 a photo")
        (season / "sheets" / "2026-10-24-g1.png").write_bytes(b"\x89PNG a photo")
        (season / "sheets" / "2026-11-14-g1.heic").write_bytes(b"a phone photo")
    return data


@pytest.fixture
def masters(tmp_path):
    return masters_folder(tmp_path)


@pytest.fixture
def converted(tmp_path, masters):
    """(result, output folder) of converting the small Masters folder, without photos."""
    out = tmp_path / "out"
    return convert_masters.convert(masters, out), out


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def game(out: Path, name: str, folder: str = "games", season: str = "2026-27"):
    return load(out / season / folder / f"{name}.yml")


# --------------------------------------------------------------------------- seasons, teams, players, schedule

def test_seasons_gym_becomes_venue_and_minimums_move_to_overrides(converted):
    _, out = converted
    seasons = {s["id"]: s for s in load(out / "seasons.yml")}
    real = seasons["2026-27"]
    assert real == {"id": "2026-27", "label": "2026-27", "current": True, "venue": "St. Pat's",
                    "venue_address": "1 Main St, Anytown, ON A1A 1A1",
                    "overrides": {"stats": {"minimums": {"ppg_min_games": 3, "ft_min_attempts": 10}}}}
    assert "gym" not in real and "gym_address" not in real and "ppg_min_games" not in real
    stand_in = seasons["sample-2026-27"]
    assert stand_in == {"id": "sample-2026-27", "label": "2026-27", "sample": True, "stands_in_for": "2026-27",
                        "venue": "St. Pat's"}                  # no minimums in Masters: none invented here
    past = seasons["sample-2025-26"]
    assert past["overrides"] == {"stats": {"minimums": {"ppg_min_games": 0}}}   # only the keys that were set
    assert list(seasons) == ["2026-27", "sample-2026-27", "sample-2025-26"]    # order kept


def test_a_season_key_with_no_place_is_left_out_and_said(tmp_path, masters):
    (masters / "seasons.yml").write_text(SEASONS + "  coach_phone: 555-0100\n", encoding="utf-8")
    result = convert_masters.convert(masters, tmp_path / "out")
    assert any("coach_phone" in line and "left out" in line for line in result.omitted)
    assert "coach_phone" not in (tmp_path / "out" / "seasons.yml").read_text(encoding="utf-8")


def test_teams_short_becomes_code_and_colour_slot_becomes_slot(converted):
    _, out = converted
    assert load(out / "2026-27" / "teams.yml") == [
        {"id": "aa", "name": "Alpha", "code": "AL", "slot": 1},
        {"id": "bb", "name": "Bravo", "code": "BR", "slot": 2}]
    text = (out / "2026-27" / "teams.yml").read_text(encoding="utf-8")
    assert "colour" not in text and "#" not in text.replace("# Converted", "")   # the hex records are dropped


def test_players_display_becomes_name(converted):
    _, out = converted
    players = {p["id"]: p for p in load(out / "2026-27" / "players.yml")}
    assert players["al-a"] == {"id": "al-a", "name": "Al A.", "team": "aa", "number": 4}
    assert players["sam-s"] == {"id": "sam-s", "name": "Sam S.", "team": "bb", "sub": True}
    assert "display" not in players["al-a"]
    assert players["abe-z"]["number"] == "00"                    # a text number stays text
    assert all("sub" not in p or p["sub"] is True for p in players.values())   # `sub: false` is just left out


def test_an_empty_players_file_converts(converted):
    _, out = converted
    assert load(out / "sample-2026-27" / "players.yml") is None      # a comment only: the core reads it as no players


def test_schedule_gym_column_is_named_venue_and_every_cell_is_kept(converted):
    _, out = converted
    text = (out / "2026-27" / "schedule.csv").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "game_id,date,time,venue,home,away,type,week,status,round"
    assert "2026-10-24-g1,2026-10-24,11:15,Annex,bb,aa,regular,2,," in lines          # the gym cell is the venue
    assert "2026-11-21-g1,2026-11-21,09:45,,aa,bb,regular,2,cancelled," in lines
    assert '2026-11-28-g1,2026-11-28,09:45,,aa,bb,playoff,6,,"Semifinal, G1"' in lines   # a comma stays quoted
    assert "2026-12-05-g1,2026-12-05,09:45,,1st,Winner G41,playoff,7,,Final" in lines    # playoff placeholders
    # cell for cell the Masters file, with the one column renamed
    original = list(csv.reader(io.StringIO(SCHEDULE)))
    original[0][original[0].index("gym")] = "venue"
    assert list(csv.reader(io.StringIO(text))) == original


def test_a_schedule_without_the_optional_columns_still_converts(tmp_path, masters):
    short = "game_id,date,time,gym,home,away,type,week\n2026-10-17-g1,2026-10-17,09:45,,aa,bb,regular,1\n"
    (masters / "2026-27" / "schedule.csv").write_text(short, encoding="utf-8")
    convert_masters.convert(masters, tmp_path / "out")
    assert (tmp_path / "out" / "2026-27" / "schedule.csv").read_text(encoding="utf-8").splitlines()[0] == \
        "game_id,date,time,venue,home,away,type,week"


# --------------------------------------------------------------------------- game files

def test_a_game_file_moves_its_boxes_under_sheet_keyed_by_side(converted):
    _, out = converted
    g = game(out, "2026-10-17-g1")
    assert list(g) == ["game_id", "status", "home", "away", "scorekeeper", "checked_by", "sheet"]
    assert (g["game_id"], g["status"], g["home"], g["away"]) == ("2026-10-17-g1", "final", "aa", "bb")
    assert (g["scorekeeper"], g["checked_by"]) == ("Pat S.", "Lee M.")
    assert "form" not in g and "teams" not in g and "running" not in g           # form dropped; the rest moved
    sheet = g["sheet"]
    assert list(sheet) == ["players", "running", "lines", "boxes"]
    assert set(sheet["players"]) == {"home", "away"}
    assert sheet["players"]["home"][0] == {"player": "al-a", "num": 4, "here": True, "ft": "MXM", "fouls": 2}
    assert sheet["players"]["away"][0] == {"player": "bo-c", "num": 5, "here": True, "ft": "M", "fouls": 3, "tech": 1}
    assert sheet["players"]["home"][3] == {"player": "ari-d", "num": 7, "here": False}
    assert sheet["running"]["home"][22] == 22 and sheet["running"]["away"][19] == 5     # int keys stay ints
    assert sheet["lines"] == {"home": [5, 12, 17, 22], "away": [5, 10, 16, 19]}
    assert sheet["boxes"]["home"] == {"q1": 5, "q2": 12, "q3": 17, "q4": 22, "ot": None, "final": 22}
    assert "notes" not in sheet


def test_the_converted_file_is_the_masters_file_with_team_ids_for_sides(converted, masters):
    """Nothing is lost or changed in the move: undoing the mapping gives back the Masters file (less `form`)."""
    _, out = converted
    for path in sorted((masters / "2026-27" / "games").glob("*.yml")) + sorted((masters / "2026-27" / "drafts").glob("*.yml")):
        original = yaml.safe_load(path.read_text(encoding="utf-8"))
        folder = path.parent.name
        converted_file = game(out, path.stem, folder)
        assert unconvert(converted_file, original) == without_form(original), path.name


def without_form(masters_game):
    return {k: v for k, v in masters_game.items() if k != "form"}


def unconvert(g, original):
    """The inverse of the mapping, for the test: sides back to the team ids, `sheet` flattened. The envelope's
    own `notes` of a forfeit were left out on purpose, so they come from the original."""
    ids = {"home": g["home"], "away": g["away"]}
    back = {k: v for k, v in g.items() if k != "sheet"}
    if "review" in back:
        back["review"] = original["review"]                  # the paths are checked on their own
    if "forfeit" in g:
        back["notes"] = original.get("notes")
        if back["notes"] is None:
            del back["notes"]
        return back
    sheet = g["sheet"]
    back["teams"] = {ids.get(side, side): {"players": rows} for side, rows in sheet["players"].items()}
    for part in ("running", "lines", "boxes"):
        if part in sheet:
            back[part] = {ids.get(side, side): v for side, v in sheet[part].items()}
    if "notes" in sheet:
        back["notes"] = [{("team" if k == "side" else k): (ids.get(v, v) if k == "side" else v)
                          for k, v in note.items()} for note in sheet["notes"]]
    return back


def test_a_notes_entry_gets_side_instead_of_team(converted):
    _, out = converted
    notes = game(out, "2026-10-24-g1")["sheet"]["notes"]
    assert notes[0] == {"side": "away", "num": "00", "q": 3, "kind": "flagrant",
                        "text": "elbow on a rebound: no foul called"}
    assert notes[1] == {"side": "home", "num": 5, "q": "OT", "kind": "note", "text": "bench warned, twice"}
    # a team that is not in the game stays as written, so the rules report it at the same box Masters did
    assert notes[2]["side"] == "zz"
    assert all("team" not in n for n in notes)


def test_sides_follow_home_and_away_not_the_order_of_the_file(converted):
    _, out = converted
    sheet = game(out, "2026-10-24-g1")["sheet"]
    assert sheet["players"]["home"][0]["player"] == "bo-c"          # bb is home in this game
    assert sheet["players"]["away"][0]["player"] == "abe-z"
    assert sheet["running"]["away"] == {1: "00", 3: 4}
    assert sheet["boxes"]["home"]["final"] == 3


def test_text_jersey_numbers_stay_text(converted):
    _, out = converted
    sheet = game(out, "2026-10-24-g1")["sheet"]
    assert sheet["players"]["away"][0]["num"] == "00" and sheet["running"]["away"][1] == "00"
    assert sheet["players"]["home"][0]["num"] == 5                  # and numbers stay numbers


def test_a_draft_keeps_a_sub_written_in_by_hand_and_its_review(converted):
    _, out = converted
    draft = game(out, "2026-10-31-g1", "drafts")
    assert draft["status"] == "draft"
    assert draft["sheet"]["players"]["away"][1] == {"num": 31, "name": "Jim K.", "here": True}
    assert "lines" in draft["sheet"] and set(draft["sheet"]["lines"]) == {"away"}      # missing lines stay missing
    assert draft["sheet"]["boxes"]["home"]["q2"] is None
    assert "checked_by" not in draft


@pytest.mark.parametrize("masters_path, expected", [
    ("running.bb.6", "sheet.running.away.6"),
    ("teams.bb.players.1", "sheet.players.away.1"),
    ("teams.bb.players.0.ft.2", "sheet.players.away.0.ft.2"),
    ("teams.aa.players.0.fouls", "sheet.players.home.0.fouls"),
    ("teams.bb", "sheet.players.away"),
    ("teams", "sheet.players"),
    ("lines.aa", "sheet.lines.home"),
    ("lines.bb.1", "sheet.lines.away.1"),
    ("boxes.aa.final", "sheet.boxes.home.final"),
    ("boxes.bb.ot", "sheet.boxes.away.ot"),
    ("running", "sheet.running"),
    ("notes", "sheet.notes"),
    ("notes.0", "sheet.notes.0"),
    ("notes.0.team", "sheet.notes.0.side"),
    ("notes.2.num", "sheet.notes.2.num"),
    ("checked_by", "checked_by"),
    ("game_id", "game_id"),
    ("scorekeeper", "scorekeeper"),
    ("status", "status"),
    ("home", "home"),
    ("form", ""),
    ("teams.zz.players.0", "sheet.players.zz.0"),         # not a team in the game: kept, so the check can say so
    ("something.else", "something.else"),                 # unknown: left as written
])
def test_review_paths_are_mapped_to_the_same_box(masters_path, expected):
    assert convert_masters.map_review_path(masters_path, {"aa": "home", "bb": "away"}) == expected


def test_a_draft_review_list_is_mapped_in_the_file(converted):
    _, out = converted
    draft = game(out, "2026-10-31-g1", "drafts")
    assert [r["at"] for r in draft["review"]] == [
        "sheet.running.away.6", "sheet.players.away.1", "sheet.players.away.0.ft.2", "sheet.lines.home",
        "sheet.lines.away.1", "sheet.boxes.home.final", "sheet.notes.0", "sheet.notes.0.side", "checked_by", ""]
    assert draft["review"][0]["note"] == "31 or 37?"                # the notes themselves are untouched


def test_a_forfeit_keeps_the_envelope_and_has_no_sheet_or_notes(converted):
    result, out = converted
    g = game(out, "2026-11-14-g1")
    assert g == {"game_id": "2026-11-14-g1", "status": "final", "home": "aa", "away": "bb", "forfeit": "bb",
                 "checked_by": "Lee M."}
    text = (out / "2026-27" / "games" / "2026-11-14-g1.yml").read_text(encoding="utf-8")
    assert "sheet" not in text and "had three players" not in text and "friendly" not in text
    left_out = [line for line in result.omitted if "2026-11-14-g1" in line]
    assert len(left_out) == 2
    assert "bb had three players at 9:55" in left_out[0] and "aa agreed to play a friendly" in left_out[1]
    assert left_out[0].startswith("2026-27/games/2026-11-14-g1.yml: notes.0")


def test_a_forfeit_draft_keeps_its_review_with_the_paths_unchanged(converted):
    result, out = converted
    g = game(out, "2026-11-07-g1", "drafts")
    assert g["forfeit"] == "aa" and "sheet" not in g and "notes" not in g
    assert [r["at"] for r in g["review"]] == ["forfeit", "notes.0"]
    assert any("2026-11-07-g1" in line and "no show" in line for line in result.omitted)


def test_a_key_the_format_does_not_have_is_kept_so_the_check_reports_it(tmp_path, masters):
    odd = CLEAN.replace("checked_by: Lee M.", "checked_by: Lee M.\ncoach: Sam T.\nrunning_extra: 1")
    odd = odd.replace("{player: al-a, num: 4, here: true, ft: MXM, fouls: 2}",
                      "{player: al-a, num: 4, here: true, ft: MXM, fouls: 2, assists: 3}")
    (masters / "2026-27" / "games" / "2026-10-17-g1.yml").write_text(odd, encoding="utf-8")
    convert_masters.convert(masters, tmp_path / "out")
    g = game(tmp_path / "out", "2026-10-17-g1")
    assert g["coach"] == "Sam T." and g["running_extra"] == 1                 # the core reports an unknown envelope key
    assert g["sheet"]["players"]["home"][0]["assists"] == 3                   # the sport reports an unknown row key


def test_a_team_entry_with_more_than_players_is_kept_whole(tmp_path, masters):
    odd = CLEAN.replace("  bb:\n    players:", "  bb:\n    coach: Sam T.\n    players:")
    (masters / "2026-27" / "games" / "2026-10-17-g1.yml").write_text(odd, encoding="utf-8")
    convert_masters.convert(masters, tmp_path / "out")
    away = game(tmp_path / "out", "2026-10-17-g1")["sheet"]["players"]["away"]
    assert away["coach"] == "Sam T." and len(away["players"]) == 3            # not a list: the rules report it


def test_game_files_are_compact_and_valid_yaml(converted):
    _, out = converted
    text = (out / "2026-27" / "games" / "2026-10-17-g1.yml").read_text(encoding="utf-8")
    assert text.startswith("game_id: 2026-10-17-g1\nstatus: final\nhome: aa\naway: bb\n")
    assert "  running:\n    home: {2: 4," in text
    assert "      - {player: al-a, num: 4, here: true, ft: MXM, fouls: 2}" in text
    assert len(text) < 3000                                                  # small enough for a link, as Masters


# --------------------------------------------------------------------------- photos

def test_photos_are_copied_only_with_the_flag(tmp_path, masters):
    plain = convert_masters.convert(masters, tmp_path / "plain")
    assert not (tmp_path / "plain" / "2026-27" / "sheets").exists()
    assert not any("sheets" in f for f in plain.files)
    with_photos = convert_masters.convert(masters, tmp_path / "photos", photos=True)
    sheets = tmp_path / "photos" / "2026-27" / "sheets"
    assert sorted(p.name for p in sheets.iterdir()) == ["2026-10-17-g1.jpg", "2026-10-24-g1.png"]
    assert (sheets / "2026-10-17-g1.jpg").read_bytes() == b"\xff\xd8 a photo"
    assert any("2026-11-14-g1.heic" in line for line in with_photos.omitted)    # a format that is not published: said
    assert not any(".gitkeep" in line for line in with_photos.omitted)          # but placeholders are not noise
    assert not (tmp_path / "photos" / "sample-2026-27" / "sheets").exists()    # no photos, no folder


# --------------------------------------------------------------------------- refusing, and reporting errors

def test_a_folder_that_already_has_files_is_refused_and_untouched(tmp_path, masters):
    out = tmp_path / "out"
    out.mkdir()
    (out / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(convert_masters.ConvertError) as exc:
        convert_masters.convert(masters, out)
    assert "already has files" in str(exc.value)
    assert sorted(p.name for p in out.iterdir()) == ["notes.txt"]
    assert (out / "notes.txt").read_text(encoding="utf-8") == "keep me"


def test_converting_twice_into_the_same_folder_is_refused(tmp_path, masters):
    convert_masters.convert(masters, tmp_path / "out")
    with pytest.raises(convert_masters.ConvertError):
        convert_masters.convert(masters, tmp_path / "out")


def test_an_empty_or_new_folder_is_fine(tmp_path, masters):
    (tmp_path / "empty").mkdir()
    convert_masters.convert(masters, tmp_path / "empty")
    convert_masters.convert(masters, tmp_path / "deep" / "new" / "folder")
    assert (tmp_path / "empty" / "seasons.yml").is_file() and (tmp_path / "deep" / "new" / "folder" / "seasons.yml").is_file()


def test_the_source_folder_is_never_written(tmp_path, masters):
    before = sorted((p.relative_to(masters).as_posix(), p.read_bytes()) for p in masters.rglob("*") if p.is_file())
    convert_masters.convert(masters, tmp_path / "out", photos=True)
    after = sorted((p.relative_to(masters).as_posix(), p.read_bytes()) for p in masters.rglob("*") if p.is_file())
    assert before == after


def test_output_inside_the_source_or_the_source_inside_the_output_is_refused(tmp_path, masters):
    with pytest.raises(convert_masters.ConvertError):
        convert_masters.convert(masters, masters / "converted")
    assert not (masters / "converted").exists()


def test_a_missing_season_folder_stops_before_anything_is_written(tmp_path, masters):
    (masters / "sample-2025-26" / "teams.yml").unlink()
    out = tmp_path / "out"
    with pytest.raises(convert_masters.ConvertError) as exc:
        convert_masters.convert(masters, out)
    assert "teams.yml: file is missing" in str(exc.value)
    assert not out.exists()


def test_every_unreadable_file_is_listed(tmp_path, masters):
    (masters / "2026-27" / "games" / "2026-10-17-g1.yml").write_text("game_id: [oops\n", encoding="utf-8")
    (masters / "2026-27" / "players.yml").write_text("- {id: x\n", encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(convert_masters.ConvertError) as exc:
        convert_masters.convert(masters, out)
    assert len(exc.value.problems) == 2 and not out.exists()


def test_not_a_masters_folder(tmp_path):
    with pytest.raises(convert_masters.ConvertError) as exc:
        convert_masters.convert(tmp_path / "nope", tmp_path / "out")
    assert "is not a folder" in str(exc.value)


# --------------------------------------------------------------------------- the command line and the preset

def test_main_prints_what_it_left_out_and_the_preset(tmp_path, masters, capsys):
    out = tmp_path / "out"
    code = convert_masters.main(["--from", str(masters), "--to", str(out)])
    text = capsys.readouterr().out
    assert code == 0
    assert "Wrote" in text and "3 games, 2 drafts" in text
    assert "Left out" in text and "bb had three players at 9:55" in text and "aa agreed to play a friendly" in text
    assert "no show" in text
    assert "Add these lines to league.yml" in text
    assert "Do not commit it" in text


def test_main_refuses_a_non_empty_folder_with_exit_code_1(tmp_path, masters, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x").write_text("x", encoding="utf-8")
    code = convert_masters.main(["--from", str(masters), "--to", str(out), "--photos"])
    captured = capsys.readouterr()
    assert code == 1 and "Nothing was written" in captured.err and "already has files" in captured.err
    assert captured.out == "" and sorted(p.name for p in out.iterdir()) == ["x"]


def test_main_photos_flag(tmp_path, masters, capsys):
    convert_masters.main(["--from", str(masters), "--to", str(tmp_path / "out"), "--photos"])
    assert (tmp_path / "out" / "2026-27" / "sheets" / "2026-10-24-g1.png").is_file()
    assert "2026-11-14-g1.heic" in capsys.readouterr().out


def test_the_preset_is_the_masters_rule_of_spec_3_4():
    preset = yaml.safe_load(convert_masters.MASTERS_PRESET)
    assert preset == {
        "rules": {"overtime": "overtime"},
        "standings": {"points": {"win": 3, "tie": 0, "loss": 0}, "period_points": 1, "ties": True,
                      "forfeit": {"score": "per_period"}, "tiebreakers": ["head_to_head", "diff"],
                      "columns": ["gp", "w", "l", "t", "pw", "pts", "diff"]}}


def test_the_script_runs_on_its_own(tmp_path, masters):
    """As the README says to run it: python sports/basketball/convert_masters.py --from ... --to ..."""
    out = tmp_path / "out"
    done = subprocess.run([sys.executable, "-B", str(SCRIPT), "--from", str(masters), "--to", str(out)],
                          capture_output=True, text=True, cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    assert (out / "2026-27" / "games" / "2026-10-17-g1.yml").is_file()
    assert "rules: {overtime: overtime}" in done.stdout and "period_points: 1" in done.stdout
    again = subprocess.run([sys.executable, "-B", str(SCRIPT), "--from", str(masters), "--to", str(out)],
                           capture_output=True, text=True, cwd=tmp_path)
    assert again.returncode == 1 and "already has files" in again.stderr


# --------------------------------------------------------------------------- checked by the basketball rules

BASKETBALL = ROOT / "sports" / "basketball"
needs_sport = pytest.mark.skipif(not (BASKETBALL / "rules.py").is_file() or not (BASKETBALL / "sport.yml").is_file(),
                                 reason="the basketball sport folder is not here yet")


@needs_sport
def test_the_converted_files_pass_the_basketball_check(tmp_path, masters):
    """The point of the converter: the core and the basketball rules accept what it writes, with the preset in
    league.yml. Games with problems on purpose (the flagrant file names a team that is not in the game) are
    removed first, so a clean report means the mapping is right."""
    (masters / "2026-27" / "games" / "2026-10-24-g1.yml").unlink()
    (masters / "2026-27" / "drafts" / "2026-11-07-g1.yml").unlink()
    data = tmp_path / "converted"
    convert_masters.convert(masters, data)
    root = tmp_path / "site"
    root.mkdir()
    (root / "sports").symlink_to(ROOT / "sports")
    (root / "league.yml").write_text(
        "name: Converter Test League\nsport: basketball\ntimezone: America/Toronto\nsample_data: false\n"
        + convert_masters.MASTERS_PRESET, encoding="utf-8")
    # the schedule rows without a game file are fine; the games with files must read cleanly
    done = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "build.py"), "--root", str(root),
                           "--data", str(data), "--check", "--today", "2026-12-01", "--json"],
                          capture_output=True, text=True, cwd=tmp_path)
    problems = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    errors = [p for p in problems if p.get("level") == "error"]
    assert done.returncode == 0 and errors == [], (done.stdout, done.stderr)
