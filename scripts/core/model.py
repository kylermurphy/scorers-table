"""The shared types (docs/stage-4-spec.md, section 3.1): `from scripts.core.model import Problem, Score, ...`.

Sports (`sports/<id>/rules.py`, `sample.py`) import these and nothing else from the core, so this module
has no imports beyond the standard library. Everything here is plain data: no I/O, no clock.
(Named `model`, not `types`: a `types.py` shadows the standard library's `types` module whenever this folder
is the current directory or on sys.path, and Python then fails to start its own imports.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Literal

LEVELS = ("error", "warning")
SIDES = ("home", "away")                                   # sheet sides, never team ids (section 2.4)
DECIDED_IN = ("regulation", "overtime", "shootout")         # Score.decided_in

# The closed vocabularies a sport's `present()` may use (section 3.4). The contract test checks against these.
PRESENT_KEYS = ("line_score", "card", "tiles", "blocks")
BLOCK_TYPES = ("stat_table", "note", "top_performer")
# The names under sport.yml `stats:` that are not groups of counting stats (every other key is a group).
STAT_RESERVED = ("derived", "team", "columns")
CELL_FLAGS = ("won", "mark", "blank", "void", "open", "hammer")

# Every layout id: assets/css/layouts/<id>.css.
LAYOUTS = ("basketball", "curling", "hockey", "slopitch", "classic", "scoreboard")


@dataclass(frozen=True)
class Problem:
    """One thing wrong (or worth a look) in one file."""
    level: Literal["error", "warning"]
    at: str            # dotted path into the file: "sheet.final.home", "3.name", "" = the whole file
    message: str       # one sentence, plain words, says what to do
    file: str = ""     # set by the core ("data/2026-27/games/2026-11-05-1.yml")

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"Problem level must be one of {LEVELS}, got {self.level!r}")


@dataclass(frozen=True)
class Placeholder:
    """A setting the league has not decided ("Unset means placeholder", section 2.1)."""
    setting: str       # dotted path in league.yml: "standings.tiebreakers"
    text: str          # what the league still has to decide, in words: "Tiebreakers"


@dataclass(frozen=True)
class Team:
    """One row of teams.yml, after the loader has filled in the slot."""
    id: str
    name: str
    code: str
    slot: int = 1                  # 1-6: the layout's team-colour palette
    colour: str | None = None      # "#RRGGBB" for a team with its own colour (st-team--custom)


@dataclass(frozen=True)
class Player:
    """One row of players.yml."""
    id: str
    name: str                      # "First L." (or the literal "[placeholder]")
    team: str | None               # a team id; None for a spare with no team
    number: str | None = None      # "0" to "99" or "00", always text so "00" survives
    sub: bool = False
    position: str | None = None    # only for sports that list positions

    @property
    def label(self) -> str:
        """How pages show the player: "#7 Ann B." with a number, "Ann B." without."""
        return f"#{self.number} {self.name}" if self.number is not None else self.name


@dataclass(frozen=True)
class SportContext:
    """Everything a sport may know, read-only."""
    sport: dict                    # its own sport.yml, parsed
    options: dict                  # league rules after defaults and season overrides
    teams: dict[str, Team]         # this season's teams
    players: dict[str, Player]
    sides: dict[str, str]          # {"home": "otters", "away": "ravens"}
    game_type: str                 # "regular" | "playoff"
    folder: str                    # "games" | "drafts" (a draft may leave boxes empty)


@dataclass
class Score:
    final: dict[str, int]                                           # {"home": 21, "away": 20}
    periods: dict[str, list[int | None]]                            # regulation periods; None = not played (X)
    extra: dict[str, list[int]] = field(default_factory=dict)       # overtime / extra ends / extra innings
    decided_in: str = "regulation"                                  # "regulation" | "overtime" | "shootout"
    final_at: dict[str, str] = field(default_factory=dict)          # the box holding each final score; both
                                                                    # sides required (call_sport checks it)


@dataclass
class Line:
    """One player's counting stats in one game."""
    side: str                      # "home" | "away"
    player: str                    # a players.yml id
    group: str = "player"          # hockey: "skater" | "goalie"
    counts: dict[str, int] = field(default_factory=dict)            # keys from sport.yml stats.<group>; gp is the core's


@dataclass
class Reading:
    score: Score
    lines: list[Line] = field(default_factory=list)                 # a player with no line did not play
    team_lines: dict[str, dict[str, int]] = field(default_factory=dict)   # per side: team counting stats
    facts: dict = field(default_factory=dict)                       # anything present() needs later


@dataclass(frozen=True)
class SampleGame:
    """What `sample.sheet()` is asked to write (section 3.6)."""
    game_id: str
    players: dict[str, list[str]]  # {"home": [player ids], "away": [...]}: who played, per side
    outcome: str                   # "win_home" | "win_away" | "tie" | "ot"


@dataclass(frozen=True)
class SportDef:
    """A sport folder, loaded (scripts/core/sports.py makes these)."""
    id: str
    folder: Path
    spec: dict                     # sport.yml, parsed and checked, optional top-level keys filled in
    rules: ModuleType              # sports/<id>/rules.py: check, read, present, derive
    sample: ModuleType | None = None   # sports/<id>/sample.py, when it was asked for

    @property
    def name(self) -> str:
        return self.spec["name"]


@dataclass(frozen=True)
class League:
    """league.yml after validation and defaults: the one object the rest of the build reads."""
    name: str
    short_name: str
    code: str
    sport: str                     # the sport's folder id
    layout: str
    colour: str | None             # "#RRGGBB", upper case
    colour_dark: str | None
    logo: str | None               # repo path, checked to exist
    tagline: str
    footer_line: str | None        # None: the active season's venue
    contact: str | None
    contact_href: str | None       # "mailto:..." or the URL
    timezone: str
    time_format: str               # "12h" | "24h"
    lang: str
    search_engines: bool
    sample_data: bool
    preview: bool
    photos: bool
    rules: dict                    # sport options: league.yml over the sport's defaults
    standings: dict                # fully filled in (see config.normalise_standings)
    standings_merged: dict         # sport defaults + league.yml before ot_* are filled; seasons merge over this
    minimums: dict[str, int]       # stats.minimums by name
    labels: dict[str, str]         # section labels: sport, then layout, then league.yml
    game_minutes: int
    github: dict | None            # {"repo": ..., "branch": ...}, passed through
    placeholders: tuple[Placeholder, ...]
    sport_def: SportDef
    nightly_hour: int = 3          # local hour (0-23) of the nightly rebuild; read by scripts/nightly_gate.py
    sport_previews: tuple[str, ...] = ()   # sport ids to build a demo copy for at /<id>/ (scripts/build_preview.sh)
