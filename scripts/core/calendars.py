"""Calendar files (iCalendar, .ics) for the real season's schedule (docs/stage-4-spec.md 4.3).

`build_calendars()` is pure: it takes the schedule as plain `CalGame` rows and returns `{file name: text}`, one
file per team and `league.ics`. `compute.py` supplies the rows from the `current` season (even while the site
shows the sample season: nobody should subscribe to made-up games) and `writer.py` writes the files.

* One event per game. The UID is made from the `game_id` (and the site's host), never from the date, so a game
  that moves keeps its UID and a calendar app that has subscribed updates the event in place (a moved game also
  carries `SEQUENCE:1` and says where it moved from).
* Times are written in UTC, worked out from the league's time zone with `zoneinfo` for that day, so a game at
  7:00 PM is the right instant on both sides of a daylight-saving change. No VTIMEZONE block is needed.
* A cancelled game stays in the feed as `STATUS:CANCELLED`. A finished game's result is in the description.
* A playoff game whose teams are not known yet ("1st", "Winner SF1") is only in `league.ics`; it joins the two
  teams' files once schedule.csv names them.
* The event is `game_minutes` long. LOCATION is the venue (with the season's address when the game is at the
  season's own venue).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from urllib.parse import quote
from zoneinfo import ZoneInfo

from scripts.core import fmt

PRODID = "-//scorers-table//Schedule//EN"
CALENDAR_PATH = "/calendar/"
LEAGUE_FILE = "league.ics"


@dataclass(frozen=True)
class CalGame:
    """One schedule row, as the calendar needs it."""
    game_id: str
    date: dt.date
    time: dt.time
    home: str                      # team id, or the text of a playoff row whose team is not known yet
    away: str
    home_name: str                 # shown names (the same text for an unknown team)
    away_name: str
    teams_known: bool = True
    type: str = "regular"
    round: str | None = None
    cancelled: bool = False
    moved_from: dt.date | None = None
    venue: str = ""
    at_season_venue: bool = True   # the venue is the season's own, so the season's address applies
    result: str | None = None      # "Final: Otters 24, Ravens 22." for a finished game


def escape(text: object) -> str:
    """Escape a TEXT value (RFC 5545 section 3.3.11)."""
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    """Split a content line into pieces of at most 75 bytes (RFC 5545 section 3.1), never inside a character."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    pieces, start, limit = [], 0, 75
    while start < len(data):
        end = min(start + limit, len(data))
        while end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        pieces.append(data[start:end].decode("utf-8"))
        start, limit = end, 74                                   # later lines start with a space
    return "\r\n ".join(pieces)


def utc(day: dt.date, time: dt.time, timezone: str) -> dt.datetime:
    """The instant a wall-clock date and time in `timezone` is, as UTC."""
    return dt.datetime.combine(day, time, tzinfo=ZoneInfo(timezone)).astimezone(dt.timezone.utc)


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def host_of(site_url: str) -> str:
    return site_url.split("://", 1)[-1].split("/", 1)[0] or "localhost"


def title(game: CalGame) -> str:
    text = f"{game.home_name} vs {game.away_name}"
    if game.type == "playoff":
        text = f"Playoffs, {game.round}: {text}" if game.round else f"Playoffs: {text}"
    return f"Cancelled: {text}" if game.cancelled else text


def description(game: CalGame, league_name: str, season_label: str, site_url: str) -> str:
    notes = [f"{league_name}, {season_label} season."]
    if game.cancelled:
        notes.append("This game was cancelled.")
    elif game.result:
        notes.append(game.result)
    if game.moved_from:
        notes.append(f"Moved from {fmt.date_short(game.moved_from)}.")
    if site_url:
        notes.append(f"Schedule and standings: {site_url}/schedule/")
    return " ".join(notes)


def event(game: CalGame, *, league_name: str, season_label: str, timezone: str, game_minutes: int, site_url: str,
          address: str, now: dt.datetime) -> list[str]:
    """The VEVENT lines for one game."""
    start = utc(game.date, game.time, timezone)
    end = start + dt.timedelta(minutes=game_minutes)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{game.game_id}@{host_of(site_url)}",
        f"DTSTAMP:{stamp(now)}",
        f"DTSTART:{stamp(start)}",
        f"DTEND:{stamp(end)}",
        f"SUMMARY:{escape(title(game))}",
        f"DESCRIPTION:{escape(description(game, league_name, season_label, site_url))}",
    ]
    if site_url:
        lines.append(f"URL:{site_url}/schedule/")
    lines += ["STATUS:CANCELLED" if game.cancelled else "STATUS:CONFIRMED", "TRANSP:OPAQUE"]
    if game.moved_from:
        lines.append("SEQUENCE:1")
    where = ", ".join(x for x in (game.venue, address if game.at_season_venue else "") if x)
    if where:
        lines.append(f"LOCATION:{escape(where)}")
    lines.append("END:VEVENT")
    return lines


def calendar(name: str, timezone: str, events: list[list[str]]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{escape(name)}", f"X-WR-TIMEZONE:{timezone}", "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
             "X-PUBLISHED-TTL:PT12H"]
    for lines_of_event in events:
        lines.extend(lines_of_event)
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)


def build_calendars(*, league_name: str, season_label: str, timezone: str, game_minutes: int,
                    games: list[CalGame], teams: dict[str, str], site_url: str = "", address: str = "",
                    today: dt.date) -> dict[str, str]:
    """{file name: .ics text}: `league.ics` and `<team id>.ics` for every team. `teams` is {id: name}.
    DTSTAMP is `today` at midnight UTC, so the same data and date always give the same files."""
    site_url = site_url.rstrip("/")
    now = dt.datetime.combine(today, dt.time(), tzinfo=dt.timezone.utc)
    events = {g.game_id: event(g, league_name=league_name, season_label=season_label, timezone=timezone,
                               game_minutes=game_minutes, site_url=site_url, address=address, now=now)
              for g in games}
    files = {LEAGUE_FILE: calendar(f"{league_name} {season_label}", timezone, [events[g.game_id] for g in games])}
    for team_id, name in teams.items():
        mine = [events[g.game_id] for g in games if g.teams_known and team_id in (g.home, g.away)]
        files[f"{team_id}.ics"] = calendar(f"{name} · {league_name} {season_label}", timezone, mine)
    return files


def links(file_name: str, label: str, team: str | None, site_url: str) -> dict:
    """The entry of calendars.json for one file: where it is on the site, and the subscribe links when the
    site's address is known (webcal:// for calendar apps, a Google Calendar link, the https download)."""
    path = f"{CALENDAR_PATH}{file_name}"
    site_url = site_url.rstrip("/")
    absolute = f"{site_url}{path}" if site_url else None
    webcal = "webcal://" + absolute.split("://", 1)[-1] if absolute else None
    google = "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe="") if webcal else None
    return {"team": team, "name": label, "path": path, "webcal": webcal, "google": google,
            "download": absolute or path}
