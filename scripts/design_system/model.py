"""Shared types and tiny helpers for the design-system specimens.

A specimen is the reference markup for one part (docs/design.md, "Part anatomy"),
filled from the sample data. Stage 4 rewrites each one as a Jekyll include.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Callable, Optional, Sequence

SPORTS = ("basketball", "curling", "hockey", "slopitch")


@dataclass
class Ctx:
    """What a specimen is rendered for."""

    layout: str          # layout id: basketball curling hockey slopitch classic scoreboard
    theme: str           # "light" | "dark" (only the wrapper differs; markup is identical)
    sport: str           # sport id: key of sample.LEAGUES
    league: dict         # sample.LEAGUES[sport]
    layout_meta: dict    # the sample.LAYOUTS entry


@dataclass
class Part:
    id: str                              # anchor id, e.g. "result-card"
    title: str                           # "Result card"
    group: str                           # "Shell" | "Scores" | "Data"
    render: Callable[[Ctx], str]         # returns the part's HTML (no wrapper)
    # Which sports to render for each layout:
    #   "layout": the sports the layout is shown with (sample.LAYOUTS[..]["sports"])
    #   "all":    all four sports in every layout (use for the line score)
    #   tuple:    exactly these sports in every layout
    sports: object = "layout"
    note: str = ""                       # one line shown under the title (what to look for)
    layouts: Optional[Sequence[str]] = None  # restrict to some layouts (e.g. ticker: scoreboard)


def esc(text) -> str:
    return escape(str(text), quote=True)


def team_by_id(league: dict, team_id: str) -> dict:
    for team in league["teams"]:
        if team["id"] == team_id:
            return team
    raise KeyError(team_id)


def chip(team: dict, size: str = "") -> str:
    """Palette colour chip for a sample team (sample teams carry `slot` 1-6)."""
    mod = f" st-chip--{size}" if size else ""
    return f'<span class="st-chip{mod} st-team--{team["slot"]}" aria-hidden="true"></span>'


MOON_SVG = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>'
)
SUN_SVG = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
    'M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
)
