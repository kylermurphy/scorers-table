"""Tests for scripts/core/calendars.py and the calendar part of the build: per-team and league files, stable UIDs
(a moved game keeps its UID), UTC times across a daylight-saving change (America/Toronto, March and November),
cancelled games, playoff rows whose teams are not known yet, location, event length, and the files a real build
writes (calendars always come from the `current` season, even while the site shows the sample).
"""
import datetime as dt
import re
import shutil
from pathlib import Path

from scripts import build
from scripts.core.calendars import CalGame, build_calendars, escape, fold, links, utc

ROOT = Path(__file__).resolve().parent.parent
TZ = "America/Toronto"
TEAMS = {"otters": "Otters", "ravens": "Ravens", "moose": "Moose"}


def game(game_id="2026-11-05-1", date=dt.date(2026, 11, 5), time=dt.time(19, 0), home="otters", away="ravens", **kw):
    names = {**TEAMS, **kw.pop("names", {})}
    return CalGame(game_id, date, time, home, away, names.get(home, home), names.get(away, away), **kw)


def files(*games, site_url="https://example.org/league", tz=TZ, minutes=60, address="1 Main St", teams=None):
    return build_calendars(league_name="Example Valley Stub League", season_label="2026–27", timezone=tz,
                           game_minutes=minutes, games=list(games), teams=teams or TEAMS, site_url=site_url,
                           address=address, today=dt.date(2026, 10, 1))


def unfold(text: str) -> str:
    return text.replace("\r\n ", "")


def event(text: str, uid_start: str = "") -> dict[str, str]:
    """The properties of the first VEVENT (whose UID starts with uid_start) as {name: value}."""
    blocks = unfold(text).split("BEGIN:VEVENT\r\n")[1:]
    block = next(b for b in blocks if b.split("\r\n")[0].startswith("UID:" + uid_start))
    return dict(line.split(":", 1) for line in block.split("END:VEVENT")[0].strip().split("\r\n"))


# ------------------------------------------------------------------ files

def test_one_file_per_team_and_the_league():
    out = files(game(), game("2026-11-12-1", dt.date(2026, 11, 12), home="moose", away="otters"))
    assert sorted(out) == ["league.ics", "moose.ics", "otters.ics", "ravens.ics"]
    assert out["league.ics"].count("BEGIN:VEVENT") == 2
    assert out["otters.ics"].count("BEGIN:VEVENT") == 2
    assert out["ravens.ics"].count("BEGIN:VEVENT") == 1
    assert out["moose.ics"].count("BEGIN:VEVENT") == 1
    assert "X-WR-CALNAME:Ravens · Example Valley Stub League 2026–27" in unfold(out["ravens.ics"])


def test_files_are_proper_ics():
    text = files(game())["league.ics"]
    assert text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert "\n" not in text.replace("\r\n", "")
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


def test_same_input_gives_the_same_bytes():
    assert files(game()) == files(game())


def test_empty_season_still_makes_valid_files():
    out = files()
    assert out["league.ics"].count("BEGIN:VEVENT") == 0 and "END:VCALENDAR" in out["league.ics"]


# ------------------------------------------------------------------ UIDs

def test_uid_comes_from_the_game_id_and_the_site_host():
    assert event(files(game())["league.ics"])["UID"] == "2026-11-05-1@example.org"


def test_uid_without_a_site_url_uses_localhost():
    assert event(files(game(), site_url="")["league.ics"])["UID"] == "2026-11-05-1@localhost"


def test_a_moved_game_keeps_its_uid_and_says_it_moved():
    before = event(files(game())["otters.ics"])
    moved = game(date=dt.date(2026, 11, 12), moved_from=dt.date(2026, 11, 5))
    after = event(files(moved)["otters.ics"])
    assert after["UID"] == before["UID"]
    assert after["DTSTART"] != before["DTSTART"]
    assert after["SEQUENCE"] == "1" and "SEQUENCE" not in before
    assert "Moved from Thu Nov 5." in after["DESCRIPTION"]


# ------------------------------------------------------------------ time zones

def test_utc_follows_the_clock_change_in_march():
    # Toronto: EST (UTC-5) until Sunday 14 March 2027, then EDT (UTC-4).
    before = event(files(game(date=dt.date(2027, 3, 11)))["league.ics"])
    after = event(files(game(date=dt.date(2027, 3, 18)))["league.ics"])
    assert before["DTSTART"] == "20270312T000000Z"       # 19:00 EST
    assert after["DTSTART"] == "20270318T230000Z"        # 19:00 EDT


def test_utc_follows_the_clock_change_in_november():
    # Toronto: EDT until Sunday 1 November 2026, then EST.
    before = event(files(game(date=dt.date(2026, 10, 29)))["league.ics"])
    after = event(files(game(date=dt.date(2026, 11, 5)))["league.ics"])
    assert before["DTSTART"] == "20261029T230000Z"       # 19:00 EDT
    assert after["DTSTART"] == "20261106T000000Z"        # 19:00 EST


def test_utc_helper_and_a_zone_without_daylight_saving():
    assert utc(dt.date(2026, 7, 1), dt.time(12, 0), "UTC") == dt.datetime(2026, 7, 1, 12, tzinfo=dt.timezone.utc)
    assert utc(dt.date(2026, 1, 1), dt.time(9, 30), "Asia/Kolkata").strftime("%H:%M") == "04:00"


def test_event_length_is_game_minutes():
    ev = event(files(game(), minutes=90)["league.ics"])
    assert (ev["DTSTART"], ev["DTEND"]) == ("20261106T000000Z", "20261106T013000Z")


# ------------------------------------------------------------------ cancelled, results, location

def test_cancelled_game_stays_as_cancelled():
    ev = event(files(game(cancelled=True))["league.ics"])
    assert ev["STATUS"] == "CANCELLED"
    assert ev["SUMMARY"].startswith("Cancelled: Otters vs Ravens")
    assert "cancelled" in ev["DESCRIPTION"]


def test_confirmed_game_and_result_in_the_description():
    ev = event(files(game(result="Final: Otters 24, Ravens 22."))["league.ics"])
    assert ev["STATUS"] == "CONFIRMED"
    assert "Final: Otters 24\\, Ravens 22." in ev["DESCRIPTION"]
    assert ev["URL"] == "https://example.org/league/schedule/"


def test_location_is_the_venue_and_the_season_address():
    with_address = event(files(game(venue="Main Gym"))["league.ics"])
    elsewhere = event(files(game(venue="Other Gym", at_season_venue=False))["league.ics"])
    address_only = event(files(game(venue=""))["league.ics"])
    unknown = event(files(game(venue="", at_season_venue=False))["league.ics"])
    assert with_address["LOCATION"] == "Main Gym\\, 1 Main St"
    assert elsewhere["LOCATION"] == "Other Gym"
    assert address_only["LOCATION"] == "1 Main St"
    assert "LOCATION" not in unknown


# ------------------------------------------------------------------ playoffs with teams not known yet

def test_placeholder_playoff_rows_are_only_in_the_league_file():
    unknown = game("2027-01-07-1", dt.date(2027, 1, 7), home="1st", away="4th", type="playoff", round="Semifinal",
                   teams_known=False)
    known = game("2027-01-14-1", dt.date(2027, 1, 14), type="playoff", round="Final")
    out = files(unknown, known)
    assert "UID:2027-01-07-1@example.org" in out["league.ics"]
    assert event(out["league.ics"], "2027-01-07")["SUMMARY"] == "Playoffs\\, Semifinal: 1st vs 4th"
    for name in ("otters.ics", "ravens.ics"):
        assert "2027-01-07-1" not in out[name] and "2027-01-14-1" in out[name]
    assert "2027-01-07-1" not in out["moose.ics"]


# ------------------------------------------------------------------ text rules and links

def test_escape_and_fold():
    assert escape("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    long = "SUMMARY:" + "é" * 60
    pieces = fold(long).split("\r\n ")
    assert len(pieces) > 1 and all(len(p.encode()) <= 75 for p in pieces) and "".join(pieces) == long


def test_links_with_and_without_the_site_address():
    full = links("otters.ics", "Otters", "otters", "https://example.org/league/")
    assert full["path"] == "/calendar/otters.ics"
    assert full["webcal"] == "webcal://example.org/league/calendar/otters.ics"
    assert full["google"] == ("https://calendar.google.com/calendar/r?cid="
                              "webcal%3A%2F%2Fexample.org%2Fleague%2Fcalendar%2Fotters.ics")
    assert full["download"] == "https://example.org/league/calendar/otters.ics"
    bare = links("league.ics", "Whole league", None, "")
    assert (bare["webcal"], bare["google"], bare["download"]) == (None, None, "/calendar/league.ics")


# ------------------------------------------------------------------ a real build

def _repo_with_a_real_season(tmp_path: Path) -> Path:
    """A repository whose real season (2026-27) holds a copy of the sample games, in Toronto time, with the
    sample on show (sample_data: true), the way the template ships."""
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(ROOT / "sports", root / "sports")
    shutil.copytree(ROOT / "data", root / "data")
    shutil.rmtree(root / "data" / "2026-27")
    shutil.copytree(ROOT / "data" / "sample-2026-27", root / "data" / "2026-27")
    text = (ROOT / "league.yml").read_text(encoding="utf-8").replace("timezone: UTC", f"timezone: {TZ}")
    (root / "league.yml").write_text(text, encoding="utf-8")
    seasons = (root / "data" / "seasons.yml").read_text(encoding="utf-8")
    (root / "data" / "seasons.yml").write_text(seasons.replace('venue: "[Gym name]"\n  venue_address: ""',
                                                               'venue: "Main Gym"\n  venue_address: "1 Main St"'),
                                               encoding="utf-8")
    return root


def test_calendars_come_from_the_current_season_even_in_sample_mode(tmp_path, capsys):
    root = _repo_with_a_real_season(tmp_path)
    out = tmp_path / "out"
    code = build.main(["--root", str(root), "--out", str(out), "--today", "2026-11-20",
                       "--site-url", "https://example.org/league"])
    capsys.readouterr()
    assert code == 0
    league = (out / "calendar" / "league.ics").read_bytes().decode("utf-8")
    assert sorted(p.name for p in (out / "calendar").iterdir()) == [
        "badgers.ics", "league.ics", "lynx.ics", "moose.ics", "otters.ics", "ravens.ics"]
    assert league.count("BEGIN:VEVENT") == 23                    # every schedule row, cancelled and playoffs too
    assert event(league, "2026-10-29-2")["STATUS"] == "CANCELLED"
    assert event(league, "2026-12-17-2")["SEQUENCE"] == "1"       # the moved game
    assert event(league, "2026-10-15-1")["LOCATION"] == "Main Gym\\, 1 Main St"
    assert "Final: Lynx 30, Ravens 21." in unfold(event(league, "2026-10-15-1")["DESCRIPTION"]).replace("\\,", ",")
    assert "Forfeit: Otters forfeited." in event(league, "2026-10-22-1")["DESCRIPTION"]
    otters = (out / "calendar" / "otters.ics").read_bytes().decode("utf-8")
    assert "2027-01-07-1" not in otters                          # a playoff row with no teams yet
    import json
    published = json.loads((out / "_data" / "computed" / "calendars.json").read_text(encoding="utf-8"))
    assert published["season"] == "2026-27"
    assert [f["team"] for f in published["files"]] == [None, "otters", "ravens", "badgers", "moose", "lynx"]
    assert published["files"][0]["webcal"] == "webcal://example.org/league/calendar/league.ics"
    # the site shows the sample season, whose teams must not link to the real season's calendars
    teams = json.loads((out / "_data" / "computed" / "sample-2026-27" / "teams.json").read_text(encoding="utf-8"))
    assert all(t["calendar"] is None for t in teams.values())


def test_a_real_season_links_its_team_calendars(tmp_path, capsys):
    root = _repo_with_a_real_season(tmp_path)
    text = (root / "league.yml").read_text(encoding="utf-8").replace("sample_data: true", "sample_data: false")
    (root / "league.yml").write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    assert build.main(["--root", str(root), "--out", str(out), "--today", "2026-11-20"]) == 0
    capsys.readouterr()
    import json
    teams = json.loads((out / "_data" / "computed" / "2026-27" / "teams.json").read_text(encoding="utf-8"))
    assert teams["otters"]["calendar"] == "/calendar/otters.ics"
    published = json.loads((out / "_data" / "computed" / "calendars.json").read_text(encoding="utf-8"))
    assert published["files"][1]["webcal"] is None              # no --site-url: no subscribe links


def test_an_empty_real_season_writes_no_calendar_files(tmp_path, capsys):
    out = tmp_path / "out"
    assert build.main(["--out", str(out), "--today", "2026-11-20"]) == 0
    capsys.readouterr()
    assert list((out / "calendar").iterdir()) == []
    assert re.search(r'"files": \[\]', (out / "_data" / "computed" / "calendars.json").read_text(encoding="utf-8"))
