"""Tests for scripts/core/fmt.py: times, dates, ordinals, numbers and the "First L." check."""
import datetime as dt
from fractions import Fraction

import pytest

from scripts.core import fmt


def test_times():
    assert fmt.format_time("19:00") == "7:00 PM"
    assert fmt.format_time("00:05") == "12:05 AM"
    assert fmt.format_time("12:30") == "12:30 PM"
    assert fmt.format_time("7:05", "24h") == "07:05"
    assert fmt.format_time(dt.time(18, 30)) == "6:30 PM"
    assert fmt.parse_time("25:00") is None and fmt.parse_time("7pm") is None and fmt.parse_time(None) is None
    with pytest.raises(ValueError):
        fmt.format_time("nope")


def test_dates_do_not_depend_on_the_locale():
    d = dt.date(2026, 11, 5)
    assert fmt.date_short(d) == "Thu Nov 5"
    assert fmt.date_long(d) == "Thursday, November 5, 2026"
    assert fmt.parse_date("2026-11-05") == d
    assert fmt.parse_date("2026-02-30") is None and fmt.parse_date("5/11/2026") is None


@pytest.mark.parametrize("n, text", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th"),
                                      (13, "13th"), (21, "21st"), (22, "22nd"), (101, "101st"), (111, "111th")])
def test_ordinal(n, text):
    assert fmt.ordinal(n) == text


def test_plural():
    assert fmt.plural(1, "game") == "1 game" and fmt.plural(0, "game") == "0 games"
    assert fmt.plural(2, "half", "halves") == "2 halves"


def test_rounding_is_half_up_not_to_even():
    assert fmt.round_half_up(2.25, 1) == 2.3 and fmt.round_half_up(0.125, 2) == 0.13
    assert fmt.decimal(Fraction(9, 4), 1) == "2.3"
    assert fmt.decimal(None) == "—"
    assert fmt.decimal(7, 1) == "7.0"


def test_signed_uses_a_real_minus():
    assert (fmt.signed(3), fmt.signed(-3), fmt.signed(0)) == ("+3", "−3", "0")


def test_win_pct_counts_a_tie_as_half_a_win():
    assert fmt.win_pct(5, 1) == ".833"
    assert fmt.win_pct(1, 0, 1) == ".750"
    assert fmt.win_pct(3, 0) == "1.000" and fmt.win_pct(0, 0) == ".000" and fmt.win_pct(0, 2) == ".000"


@pytest.mark.parametrize("name", ["Ann B.", "Mary-Jo K.", "D'Arcy O.", "Joe K.", "[placeholder]"])
def test_first_last_accepts(name):
    assert fmt.is_first_last(name)


@pytest.mark.parametrize("name", ["Ann Bell", "Ann", "ann b.", "Ann B", "Ann BB.", "", None, 5, " B."])
def test_first_last_rejects(name):
    assert not fmt.is_first_last(name)


def test_humanize():
    assert fmt.humanize("run_limit") == "Run limit"
