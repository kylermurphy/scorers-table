"""Visitors first (E26, docs/stage-5-slopitch-spec.md): with `display.matchup: at` every place that lists a game's two
teams puts the away team first and joins them with "at"; with `vs` (the default) nothing changes.

The pages are the parity site's `extras-at` / `extras-vs` / `extras-toss` pages (tests/parity/site.py): the slo-pitch
sample (home = Sluggers, away = Mudcats), run through the includes with league.sides_order [away, home], the same
games with [home, away], and a game whose line score says `first: home` (a coin toss). The game layout's title lines
are rendered as written. The calendar summary is tested on build_calendars. Needs Ruby (CI always runs it).
"""
from __future__ import annotations

import datetime as dt
import re

import pytest

from scripts.core.calendars import CalGame, build_calendars
from tests.parity import site


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    command = site.jekyll_command()
    if command is None:
        site.skip_unless_ci("test_matchup needs Ruby, Bundler and the gems: run `bundle install`")
    rendered = site.build_site(tmp_path_factory.mktemp("matchup"), command)
    out = {}
    for key in ("at", "vs", "toss"):
        blocks = rendered[("extras", f"extras-{key}")]
        parts = blocks["x-matchup"].split('<div data-t="')[1:]
        out[key] = {p.split('">', 1)[0]: p.split('">', 1)[1] for p in parts}
        out[key]["title"] = re.search(r'<p data-t="title">(.*?)</p>', blocks.get("x-title", "")).group(1) \
            if "x-title" in blocks else None
    return out


def order(html: str, *names: str) -> list[str]:
    """The names in the order they first appear in the markup."""
    return sorted(names, key=lambda n: html.index(n))


def rows(html: str) -> list[str]:
    """The team names of a line score's rows, top to bottom."""
    return re.findall(r'<span class="st-line-score__name">(?:<abbr[^>]*>)?([^<]+)', html)


@pytest.mark.jekyll
def test_the_game_title_puts_the_visitors_first(pages):
    assert pages["at"]["title"] == "Mudcats at Sluggers"
    assert pages["vs"]["title"] == "Sluggers vs Mudcats"


@pytest.mark.jekyll
@pytest.mark.parametrize("part", ["final", "card", "hero"])
def test_final_panel_and_result_rows_follow_sides_order(pages, part):
    assert order(pages["at"][part], "Sluggers", "Mudcats") == ["Mudcats", "Sluggers"]
    assert order(pages["vs"][part], "Sluggers", "Mudcats") == ["Sluggers", "Mudcats"]


@pytest.mark.jekyll
def test_the_big_score_is_in_the_same_order(pages):
    at = re.findall(r'st-final__num[^>]*>(\d+)<', pages["at"]["final"])
    vs = re.findall(r'st-final__num[^>]*>(\d+)<', pages["vs"]["final"])
    assert at == ["11", "14"] and vs == ["14", "11"]


@pytest.mark.jekyll
def test_line_score_rows_and_caption(pages):
    assert rows(pages["at"]["linescore"]) == ["Mudcats", "Sluggers"]
    assert rows(pages["vs"]["linescore"]) == ["Sluggers", "Mudcats"]
    assert rows(pages["at"]["cardscore"]) == ["Mudcats", "Sluggers"]
    assert "Mudcats 11, Sluggers 14</caption>" in pages["at"]["linescore"]
    assert "Sluggers 14, Mudcats 11</caption>" in pages["vs"]["linescore"]


@pytest.mark.jekyll
def test_a_coin_toss_line_score_puts_the_team_that_batted_first_on_top(pages):
    """`first: home` orders that game's rows (full and card), whatever the league's order is."""
    assert rows(pages["toss"]["linescore"]) == ["Sluggers", "Mudcats"]
    assert rows(pages["toss"]["cardscore"]) == ["Sluggers", "Mudcats"]
    assert "Sluggers 14, Mudcats 11</caption>" in pages["toss"]["linescore"]
    assert order(pages["toss"]["final"], "Sluggers", "Mudcats")[0] == "Mudcats"      # the head keeps the league's order
    assert rows(pages["at"]["linescore"]) == ["Mudcats", "Sluggers"]                 # another game is untouched


@pytest.mark.jekyll
def test_game_rows_and_the_next_game_panel_say_at(pages):
    for part in ("row", "panel"):
        assert re.search(r'>Long Balls <span class="st-game-row__vs">at</span> Sluggers<', pages["at"][part]), part
        assert re.search(r'>Sluggers <span class="st-game-row__vs">vs</span> Long Balls<', pages["vs"][part]), part


@pytest.mark.jekyll
def test_the_ticker_lists_the_visitors_first(pages):
    assert "MUD 11 · SLG 14" in pages["at"]["ticker"]
    assert "SLG 14 · MUD 11" in pages["vs"]["ticker"]


# ------------------------------------------------------------------ the calendar summary

def _summary(matchup: str | None, **kw) -> str:
    game = CalGame("2027-06-16-1", dt.date(2027, 6, 16), dt.time(18, 30), "sluggers", "mudcats", "Sluggers", "Mudcats", **kw)
    extra = {} if matchup is None else {"matchup": matchup}
    files = build_calendars(league_name="Maple Park", season_label="2027", timezone="America/Toronto", game_minutes=60,
                            games=[game], teams={"sluggers": "Sluggers", "mudcats": "Mudcats"}, today=dt.date(2027, 6, 1),
                            **extra)
    text = files["league.ics"].replace("\r\n ", "")
    return re.search(r"SUMMARY:(.*)\r\n", text).group(1)


def test_the_calendar_summary_is_visitors_at_home_with_at():
    assert _summary("at") == "Mudcats at Sluggers"
    assert _summary("vs") == "Sluggers vs Mudcats"
    assert _summary(None) == "Sluggers vs Mudcats"


def test_the_calendar_summary_keeps_its_playoff_and_cancelled_prefixes():
    assert _summary("at", type="playoff", round="Final") == "Playoffs\\, Final: Mudcats at Sluggers"   # a comma is escaped in .ics text
    assert _summary("at", cancelled=True) == "Cancelled: Mudcats at Sluggers"
