"""Small pure formatting helpers shared by the build: times, dates, ordinals, numbers, "First L." names.

Nothing here reads the clock, the locale or the file system, so the same input always prints the same text
(`strftime` is avoided because it follows the machine's locale).
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

MINUS = "−"        # a real minus sign, for negative numbers
DASH = "—"         # "no value"
PLACEHOLDER = "[placeholder]"

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_time(text: str) -> dt.time | None:
    """'19:00' (24 hour, as written in schedule.csv) -> a time; None when it is not one."""
    match = _TIME_RE.match(text.strip()) if isinstance(text, str) else None
    return dt.time(int(match.group(1)), int(match.group(2))) if match else None


def parse_date(text: str) -> dt.date | None:
    """'2026-11-05' -> a date; None when it is not a real date."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text.strip()):
        return None
    try:
        return dt.date.fromisoformat(text.strip())
    except ValueError:
        return None


def format_time(value: dt.time | str, time_format: str = "12h") -> str:
    """19:00 -> '7:00 PM' (time_format '12h') or '19:00' ('24h'). A '19:00' string is accepted too."""
    t = parse_time(value) if isinstance(value, str) else value
    if t is None:
        raise ValueError(f"not a time: {value!r}")
    if time_format == "24h":
        return f"{t.hour:02d}:{t.minute:02d}"
    return f"{(t.hour % 12) or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def date_short(d: dt.date) -> str:
    """'Thu Nov 5'."""
    return f"{WEEKDAYS[d.weekday()][:3]} {MONTHS[d.month - 1][:3]} {d.day}"


def date_long(d: dt.date) -> str:
    """'Thursday, November 5, 2026'."""
    return f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 11 -> '11th', 22 -> '22nd'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def plural(n: int, one: str, many: str | None = None) -> str:
    """plural(1, 'game') -> '1 game'; plural(2, 'game') -> '2 games'; plural(2, 'half', 'halves')."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def round_half_up(value: int | float | Fraction | Decimal, places: int = 1) -> float:
    """Round half up (2.25 -> 2.3), not to even; exact for ints, Fractions and Decimals."""
    if isinstance(value, Fraction):
        value = Decimal(value.numerator) / Decimal(value.denominator)
    elif isinstance(value, float):
        value = Decimal(repr(value))
    return float(Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def decimal(value: int | float | Fraction | Decimal | None, places: int = 1) -> str:
    """A fixed number of decimals, half up: 7.25 -> '7.3'; None -> '—'."""
    return DASH if value is None else f"{round_half_up(value, places):.{places}f}"


def signed(n: int) -> str:
    """+3, −3, 0 (a real minus sign)."""
    return f"+{n}" if n > 0 else f"{MINUS}{-n}" if n < 0 else "0"


def win_pct(wins: int, losses: int, ties: int = 0) -> str:
    """'.833' style; a tie counts as half a win; '1.000' unbeaten; '.000' with no games."""
    games = wins + losses + ties
    if not games:
        return ".000"
    pct = Fraction(2 * wins + ties, 2 * games)
    text = f"{round_half_up(pct, 3):.3f}"
    return text if pct == 1 else text.lstrip("0")


def is_first_last(name: object) -> bool:
    """True for 'First L.': a first name (letters, spaces, apostrophes, hyphens, full stops), a space, one
    capital letter and a full stop. The literal '[placeholder]' is allowed too (a row waiting to be filled in)."""
    if name == PLACEHOLDER:
        return True
    if not isinstance(name, str) or " " not in name:
        return False
    first, last = name.rsplit(" ", 1)
    return (bool(first.strip()) and all(c.isalpha() or c in " '’-." for c in first)
            and len(last) == 2 and last[0].isalpha() and last[0].isupper() and last[1] == ".")


def humanize(key: str) -> str:
    """'ppg_min_games' -> 'Ppg min games'; used for a setting's name when the sport gives no label."""
    text = key.replace("_", " ").strip()
    return text[:1].upper() + text[1:]
