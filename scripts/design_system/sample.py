"""Shared sample data for the design-system showcase (stage 3).

Everything here is made up and copied from the approved phone mockups
(the *.dc.html canvas files).  Plain dicts and lists only, so it reads like
JSON.  The showcase generator and every specimen function read this module;
nothing else invents data.

Run the self-check from the repo root:

    python3 -m scripts.design_system.sample
    python3 -I scripts/design_system/sample.py      # also works (stdlib only)

(`python3 -I -m scripts.design_system.sample` cannot work: isolated mode
leaves the current directory off sys.path, so `scripts` is not found.)

TOP-LEVEL NAMES
    LAYOUTS             ordered list of the six layouts
    LAYOUT_BY_ID        {layout id: layout dict}
    LEAGUES             {sport id: league dict}  (the four sample leagues)
    ALT_LEAGUE_COLOURS  example league colours for the recolouring demo
    P(number, name)     helper that builds a person dict
    team(sport, id)     helper: the team dict
    team_name(sport, id)

PEOPLE
    A person is {"number": "23" | None, "name": "Dave M.", "label": "#23 Dave M."}.
    `label` is what the page shows (number first when there is one).
    Always "First L."; never a full name.

CONVENTIONS (read these before writing a specimen)
    * Team references are team ids ("rapids", "stone_cold").  Look the team up
      in LEAGUES[sport]["teams"] for name, code, slot, record.
    * `slot` is the team's palette colour (1..6), the index into the layout's
      team palette (the order of the colour list in docs/dark-palettes.md,
      which is also the order of the dots in the light mockups).  Colours
      themselves are CSS tokens, not data.
    * `home` / `away` on a result or fixture mean the FIRST-listed (top row,
      "A vs B" left) and SECOND-listed (bottom row, right) team exactly as the
      mockup lists them.  They do NOT say who is the home team.
      `designated_home` is a team id only where a mockup says who is home
      (slo-pitch "Mudcats at Sluggers"), otherwise None.
    * Scores/period scores use None for a box that was not played (curling
      "X" ends, slo-pitch last inning "X").
    * A result's `period_scores` is None when no mockup shows its by-period
      numbers (they are never invented).
    * Text copied from a mockup keeps its characters: en dash in "2026–27",
      real minus sign in "−31", "›" after link labels.
    * `only_layouts` (on tiles/lists) means the item appears only in those
      layouts' mockups (None = all layouts).
"""

import re

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def P(number, name):
    """A person: jersey number optional, name always "First L."."""
    num = None if number is None else str(number)
    return {
        "number": num,
        "name": name,
        "label": ("#%s %s" % (num, name)) if num else name,
    }


def team(sport, team_id):
    for t in LEAGUES[sport]["teams"]:
        if t["id"] == team_id:
            return t
    raise KeyError("%s: no team %r" % (sport, team_id))


def team_name(sport, team_id):
    return team(sport, team_id)["name"]


# ---------------------------------------------------------------------------
# 1. LAYOUTS  (docs/design.md table; blurbs from the canvas overview board)
# ---------------------------------------------------------------------------

LAYOUTS = [
    {
        "id": "basketball",
        "name": "Basketball",
        "kind": "sport",
        "sports": ["basketball"],
        "fonts": ("Barlow Condensed", "Barlow"),
        "blurb": "Deep blue header with a sunrise edge and a coral active tab.",
        "palette_note": "Deep blue #032F98 header, coral #FF5C66 active tab, ink #0B1B3F, page #F4F6FB.",
    },
    {
        "id": "curling",
        "name": "Curling",
        "kind": "sport",
        "sports": ["curling"],
        "fonts": ("Alegreya", "Source Sans 3"),
        "blurb": "Pebbled ice, navy ink and the house rings, with the end-by-end line score as the hero.",
        "palette_note": "Pebbled ice #EEF4F8, navy ink #0E2233, house red #C8102E and blue #1D4E89.",
    },
    {
        "id": "hockey",
        "name": "Hockey",
        "kind": "sport",
        "sports": ["hockey"],
        "fonts": ("Saira Condensed", "Saira"),
        "blurb": "White ice, red and blue lines, dark boards and a gold kickplate.",
        "palette_note": "White ice, boards #14181F, red #C8102E and blue #1D4E89 lines, kickplate #F2A900.",
    },
    {
        "id": "slopitch",
        "name": "Slo-pitch",
        "kind": "sport",
        "sports": ["slopitch"],
        "fonts": ("Zilla Slab", "Work Sans"),
        "blurb": "Scorebook paper, infield clay and outfield green.",
        "palette_note": "Scorebook paper #FBF7EE, clay #B5532E, outfield green #2F6B3A, ink #22201C.",
    },
    {
        "id": "classic",
        "name": "Classic",
        "kind": "general",
        "sports": ["curling", "hockey"],
        "fonts": ("Barlow Condensed", "Barlow"),
        "blurb": "A white header with one bar in the league's colour: the safe choice for any sport.",
        "palette_note": "White header, one bar in the league's colour, page #F4F6FB.",
    },
    {
        "id": "scoreboard",
        "name": "Scoreboard",
        "kind": "general",
        "sports": ["slopitch", "basketball"],
        "fonts": ("Anton", "Chakra Petch"),
        "blurb": "Black with amber arena digits and a header bar in the league's colour.",
        "palette_note": "Black #111111, amber digits #FFC233, header bar in the league's colour.",
    },
]

LAYOUT_BY_ID = {l["id"]: l for l in LAYOUTS}


# ---------------------------------------------------------------------------
# 4. ALT_LEAGUE_COLOURS  (recolouring demo and the stage 4 colour check's examples)
# ---------------------------------------------------------------------------

# Example league colours (`colour` in league.yml). Every one with white text at 4.5:1 or more must
# pass every pair in every layout, both themes (scripts/check_contrast.py runs them in custom-colour
# mode). Gold is the deliberate hard case: white text on it fails AA (about 2.9:1), so the data
# check stops with a message naming `colour`; it is marked expected_fail.
ALT_LEAGUE_COLOURS = [
    {"name": "Navy", "hex": "#1D3A6E"},
    {"name": "Deep red", "hex": "#9E1B32"},
    {"name": "Forest green", "hex": "#2F6B3A"},
    {"name": "Teal", "hex": "#0E6B6B"},
    {"name": "Purple", "hex": "#5B3A8C"},
    {"name": "Brown", "hex": "#7A4A1E"},
    {"name": "Mid blue", "hex": "#1F5FA8"},
    {"name": "Gold", "hex": "#C98A12", "expected_fail": True},
]


# ---------------------------------------------------------------------------
# 2. LEAGUES
# ---------------------------------------------------------------------------

NAV = ["Home", "Schedule", "Stats", "Teams", "Archive"]
FOOTER_LINKS = ["Teams", "Past seasons", "League rules", "Contact"]
CREDIT = "Made with scorers-table"


def _tm(tid, name, code, slot, colour, hex_light, hex_dark, record, code_in_mockup=True, skip=None):
    """One team.  mockup_hex_* are reference only (CSS tokens are the truth)."""
    return {
        "id": tid,
        "name": name,
        "code": code,
        "code_in_mockup": code_in_mockup,  # False: the mockups never show this code
        "slot": slot,
        "colour": colour,
        "mockup_hex": {"light": hex_light, "dark": hex_dark},
        "record": record,
        "skip": skip,  # curling only: skip's name where a mockup shows it
    }


def _col(key, label, title, key_col=False):
    return {"key": key, "label": label, "title": title, "key_col": key_col}


# ===========================================================================
# BASKETBALL: Riverside Masters Basketball
# Copied from Basketball-Home, Basketball-Game, Scoreboard-Basketball-Home.
# ===========================================================================

BASKETBALL = {
    "sport": "basketball",
    "name": "Riverside Masters Basketball",
    "short_name": "Riverside Masters",
    "code": "RMB",
    "tagline": "Basketball · 2026–27",
    "season": "2026–27",
    "nav": NAV,
    "period_word": "Quarter",
    "period_labels": ["Q1", "Q2", "Q3", "Q4"],
    "total_label": "Final",
    "surface_word": "",
    "venue": "[Gym name]",
    "footer_name": "Riverside Masters Basketball",
    "footer_line": "Thursday evenings · [Gym name]",
    "footer_links": FOOTER_LINKS,
    "credit": CREDIT,
    "points_note": "2 points a win. Playoffs: [playoff format].",
    # Section names where a layout renames them (default names in `labels`).
    "labels": {
        "results": "Latest results",
        "next": "Next game night",
        "standings": "Standings",
        "leaders": "Leaders",
        "full_table": "Full table",
        "all_stats": "All stats",
        "score_sheets": "Score sheets (PDF) ›",
    },
    "layout_labels": {
        "scoreboard": {
            "results": "Game of the week",
            "next": "Next up",
            "standings": "The race",
            "leaders": "Buckets",
            "full_table": "Full standings",
            "all_stats": "All player stats",
        },
    },
    # Teams, in palette order (slot 1..5).
    "teams": [
        _tm("rapids", "Rapids", "RAP", 1, "blue", "#1F6FB5", "#5B9DF0", "6–1"),
        _tm("herons", "Herons", "HER", 2, "teal", "#0F7F86", "#3CC8C0", "5–2"),
        _tm("foxes", "Foxes", "FOX", 3, "orange", "#D9621A", "#FF9A52", "3–3"),
        _tm("pines", "Pines", "PIN", 4, "green", "#2E7D32", "#6CC46F", "2–4"),
        _tm("comets", "Comets", "COM", 5, "purple", "#6B3FA0", "#B08CF0", "0–6"),
    ],
    # Basketball-Home standings.  No bold key column in this mockup.
    "standings": {
        "team_label": "Team",
        "team_label_general": "Team",
        "bar": {"basis": "win_pct"},  # Scoreboard "The race": bar = win %
        "columns": [
            _col("W", "W", "Wins"),
            _col("L", "L", "Losses"),
            _col("PCT", "PCT", "Winning percentage"),
            _col("GB", "GB", "Games behind the leader"),
            _col("DIFF", "DIFF", "Point difference"),
        ],
        "rows": [
            {"team": "rapids", "values": {"W": 6, "L": 1, "PCT": ".857", "GB": "—", "DIFF": "+61"}},
            {"team": "herons", "values": {"W": 5, "L": 2, "PCT": ".714", "GB": "1", "DIFF": "+30"}},
            {"team": "foxes", "values": {"W": 3, "L": 3, "PCT": ".500", "GB": "2.5", "DIFF": "+3"}},
            {"team": "pines", "values": {"W": 2, "L": 4, "PCT": ".333", "GB": "3.5", "DIFF": "−31"}},
            {"team": "comets", "values": {"W": 0, "L": 6, "PCT": ".000", "GB": "5.5", "DIFF": "−63"}},
        ],
    },
    # Basketball-Home "Latest results".
    "results_header": {"title": "Latest results", "meta": "Week 8 · Thu Dec 3"},
    "results_legend": [],
    "bye": "foxes",  # Scoreboard ticker: "FOX bye" (week 8)
    "results": [
        {
            "id": "bb-rapids-pines",
            "home": "rapids",
            "away": "pines",
            "designated_home": None,
            "scores": {"rapids": 71, "pines": 64},
            # from Basketball-Game "Q1..Q4"
            "period_scores": {"rapids": [18, 16, 20, 17], "pines": [15, 19, 14, 16]},
            "status": "Final",
            "tie": False,
            "winner": "rapids",
            "date": "Thu Dec 3, 2026",
            "time": "7:00 PM",
            "surface": None,
            "meta": None,
            "note": "Top: #23 Dave M. 24 pts",
            "note_strong": "#23 Dave M.",
            "note_long": "Top scorer: #23 Dave M. 24 pts, 6-7 FT",  # Scoreboard featured card
            "link_label": "Box score ›",
            "game": "bb-rapids-pines",  # id of LEAGUES[...]["game"], else None
        },
        {
            "id": "bb-herons-comets",
            "home": "herons",
            "away": "comets",
            "designated_home": None,
            "scores": {"herons": 66, "comets": 52},
            "period_scores": None,  # not shown in any mockup
            "status": "Final",
            "tie": False,
            "winner": "herons",
            "date": "Thu Dec 3, 2026",
            "time": None,
            "surface": None,
            "meta": None,
            "note": "Top: #9 Rob K. 19 pts",
            "note_strong": "#9 Rob K.",
            "note_long": None,
            "link_label": "Box score ›",
            "game": None,
        },
    ],
    # Scoreboard "Game of the week" card.
    "featured": {"result": "bb-rapids-pines", "label": "Game of the week", "date": "Final · Dec 3"},
    # Basketball-Home "Next game night" (Scoreboard calls it "Next up", date "Thu Dec 10").
    "next_day": {
        "eyebrow": "Next game night",
        "label": "Thursday, Dec 10",
        "label_short": "Thu Dec 10",
        "where": "[Gym name]",
        "where_note": None,
        "week_label": "Week 9",
        "groups": [
            {
                "time_label": None,
                "rows": [
                    {"surface": None, "home": "foxes", "away": "rapids", "time": "7:00 PM"},
                    {"surface": None, "home": "pines", "away": "comets", "time": "8:15 PM"},
                ],
            }
        ],
        "bye": "herons",
        "foot": "Herons have the bye",
        "foot_link": "Score sheets (PDF) ›",
    },
    # Basketball-Home "Leaders" (+ Scoreboard "Buckets").
    "leaders": {
        "title": "Leaders",
        "tiles": [
            {
                "key": "ppg",
                "label": "Points / game",
                "value": "20.1",
                "name": "#23 Dave M.",
                "person": P(23, "Dave M."),
                "team": "rapids",
                "meta": "Rapids · 141 pts, 7 GP",
                "edge": "hot",
                "only_layouts": None,
            },
            {
                "key": "ftpct",
                "label": "Free throw %",
                "value": "90.0",
                "name": "#12 Jim F.",
                "person": P(12, "Jim F."),
                "team": "pines",
                "meta": "Pines · 18 of 20",
                "edge": "accent",
                "only_layouts": None,
            },
        ],
        # first_row_in_tile: the sport layout's list starts at rank 2 because
        # the tile above already shows rank 1; Scoreboard shows ranks 1..3.
        "lists": [
            {
                "key": "ppg",
                "title": "Points / game",
                "columns": None,
                "first_row_in_tile": True,
                "only_layouts": None,
                "note": None,
                "rows": [
                    {"rank": 1, "name": "#23 Dave M.", "person": P(23, "Dave M."), "team": "rapids",
                     "value": "20.1", "detail": "141 pts in 7 GP", "values": None},
                    {"rank": 2, "name": "#9 Rob K.", "person": P(9, "Rob K."), "team": "herons",
                     "value": "18.3", "detail": None, "values": None},
                    {"rank": 3, "name": "#7 Mike R.", "person": P(7, "Mike R."), "team": "pines",
                     "value": "17.3", "detail": None, "values": None},
                    {"rank": 4, "name": "#4 Steve P.", "person": P(4, "Steve P."), "team": "foxes",
                     "value": "16.0", "detail": None, "values": None},
                ],
            },
            {
                "key": "ftpct",
                "title": "Free throw %",
                "columns": None,
                "first_row_in_tile": True,
                "only_layouts": ["scoreboard"],
                "note": None,
                "rows": [
                    {"rank": 1, "name": "#12 Jim F.", "person": P(12, "Jim F."), "team": "pines",
                     "value": "90.0", "detail": "18 of 20", "values": None},
                ],
            },
        ],
        "note": None,
    },
}

# Basketball-Game (the Rapids vs Pines box score).
BASKETBALL["game"] = {
    "id": "bb-rapids-pines",
    "result": "bb-rapids-pines",
    "back_label": "‹ Schedule",
    "nav_current": "Schedule",
    "header": {
        "eyebrow": "Week 8 · Regular season",
        "title": "Rapids vs Pines",
        "subline": "Thu Dec 3, 2026 · 7:00 PM · [Gym name]",
        "venue_line": None,
    },
    "final": {
        "label": "Final",
        "sub": "Rapids by 7",
        "teams": [
            {"team": "rapids", "role": None, "record": "6–1", "result": "Win", "score": 71, "winner": True},
            {"team": "pines", "role": None, "record": "2–4", "result": "Loss", "score": 64, "winner": False},
        ],
    },
    "line_score": {
        "corner_label": "Team",
        "columns": ["Q1", "Q2", "Q3", "Q4", "Final"],
        "rows": [
            {"team": "rapids", "cells": [18, 16, 20, 17], "total": 71},
            {"team": "pines", "cells": [15, 19, 14, 16], "total": 64},
        ],
        # 1-based period number of each team's biggest quarter (underlined).
        "highlight": {"kind": "biggest_period", "periods": {"rapids": 3, "pines": 2}},
        "note": "Biggest quarter for each team.",
    },
    "top_scorer": {
        "label": "Top scorer",
        "player": P(23, "Dave M."),
        "team": "rapids",
        "detail": "Rapids · 6-7 free throws",
        "value": 24,
        "unit": "Points",
    },
    "box_scores": [
        {
            "team": "rapids",
            "score": 71,
            "columns": [_col("PTS", "PTS", "Points", True), _col("FT", "FTM-FTA", "Free throws made-attempted"),
                        _col("PF", "PF", "Personal fouls")],
            "number_label": "#",
            "player_label": "Player",
            "rows": [
                {"player": P(23, "Dave M."), "pts": 24, "ftm": 6, "fta": 7, "pf": 2},
                {"player": P(11, "Greg T."), "pts": 14, "ftm": 2, "fta": 4, "pf": 3},
                {"player": P(5, "Al B."), "pts": 10, "ftm": 2, "fta": 2, "pf": 1},
                {"player": P(32, "Ken W."), "pts": 9, "ftm": 1, "fta": 2, "pf": 4},
                {"player": P(8, "Paul S."), "pts": 6, "ftm": 0, "fta": 0, "pf": 2},
                {"player": P(14, "Rick D."), "pts": 4, "ftm": 2, "fta": 4, "pf": 1},
                {"player": P(21, "Tom H."), "pts": 4, "ftm": 0, "fta": 1, "pf": 3},
                {"player": P(44, "Bill C."), "pts": 0, "ftm": 0, "fta": 0, "pf": 1},
            ],
            "totals": {"label": "Team · 8 played", "pts": 71, "ftm": 13, "fta": 20, "pf": 17},
            "note": "Free throws 65.0%",
        },
        {
            "team": "pines",
            "score": 64,
            "columns": [_col("PTS", "PTS", "Points", True), _col("FT", "FTM-FTA", "Free throws made-attempted"),
                        _col("PF", "PF", "Personal fouls")],
            "number_label": "#",
            "player_label": "Player",
            "rows": [
                {"player": P(7, "Mike R."), "pts": 21, "ftm": 5, "fta": 6, "pf": 3},
                {"player": P(12, "Jim F."), "pts": 15, "ftm": 3, "fta": 3, "pf": 2},
                {"player": P(3, "Doug L."), "pts": 11, "ftm": 1, "fta": 2, "pf": 4},
                {"player": P(24, "Sam O."), "pts": 8, "ftm": 2, "fta": 2, "pf": 2},
                {"player": P(10, "Ray P."), "pts": 5, "ftm": 1, "fta": 3, "pf": 1},
                {"player": P(33, "Lou G."), "pts": 4, "ftm": 0, "fta": 0, "pf": 3},
                {"player": P(15, "Hal N."), "pts": 0, "ftm": 0, "fta": 1, "pf": 2},
            ],
            "totals": {"label": "Team · 7 played", "pts": 64, "ftm": 12, "fta": 17, "pf": 17},
            "note": "Free throws 70.6%",
        },
    ],
    "footnotes": [
        "PF = personal fouls. Points come from the running score on the score sheet; free throws from its circles."
    ],
    "calendar": {"label": "Add to calendar · Rapids schedule ›", "team": "rapids"},
}


# ===========================================================================
# CURLING: Pine Lake Curling Club
# Copied from Curling-Home, Classic-Curling-Home, Curling-Game.
# ===========================================================================

CURLING = {
    "sport": "curling",
    "name": "Pine Lake Curling Club",
    "short_name": "Pine Lake Curling Club",
    "code": "PL",
    "tagline": "Tuesday Mixed · 2026–27",
    "season": "2026–27",
    "nav": NAV,
    "period_word": "End",
    "period_labels": ["1", "2", "3", "4", "5", "6", "7", "8"],
    "total_label": "Tot",
    "surface_word": "Sheet",
    "venue": "[Club address]",
    "footer_name": "Pine Lake Curling Club",
    "footer_line": "Tuesday Mixed league",
    "footer_links": FOOTER_LINKS,
    "credit": CREDIT,
    "points_note": "2 points a win, 1 a tie. Tiebreakers: [placeholder].",
    "labels": {
        "results": "Latest draw",
        "next": "Next draw",
        "standings": "Standings",
        "leaders": "Rink leaders",
        "full_table": "Full table",
        "all_stats": "All stats",
    },
    "layout_labels": {
        # Classic-Curling-Home: leaders section is headed by its first list.
        "classic": {"leaders": "Stolen ends"},
    },
    # Teams in palette order (slot 1..6); light dots match docs/dark-palettes.md order.
    # Codes: BP and HH are in the Game mockup; the other four are initials
    # made up for the showcase (no mockup shows them).
    "teams": [
        _tm("button_pushers", "Button Pushers", "BP", 1, "red", "#C8102E", "#E8475A", "5–1–1", True, "Doug H."),
        _tm("hurry_hard", "Hurry Hard", "HH", 2, "green", "#2E7D4F", "#34A464", "4–3–0", True, "Wayne B."),
        _tm("hog_liners", "Hog Liners", "HL", 3, "blue", "#1D4E89", "#6FA3EA", "1–6–0", False, None),
        _tm("free_guards", "Free Guards", "FG", 4, "purple", "#6B3FA0", "#B391EE", "3–3–1", False, "Norm K."),
        _tm("takeouts", "Takeouts", "TO", 5, "gold", "#B07D00", "#E9B940", "1–6–0", False, None),
        _tm("stone_cold", "Stone Cold", "SC", 6, "grey", "#56636F", "#C3CDD7", "6–1–0", False, "Gail R."),
    ],
    # Curling-Home standings (Latest draw = Draw 7).  Sport layout heads the first
    # column "Rink"; Classic heads it "Team".
    "standings": {
        "team_label": "Rink",
        "team_label_general": "Team",
        "bar": {"basis": "points_of_max", "max": 14},  # 7 GP x 2 points (not shown in a curling mockup)
        "columns": [
            _col("GP", "GP", "Games played"),
            _col("W", "W", "Wins"),
            _col("L", "L", "Losses"),
            _col("T", "T", "Ties"),
            _col("PTS", "PTS", "Points", True),
            _col("PF", "PF", "Points for"),
            _col("PA", "PA", "Points against"),
        ],
        "rows": [
            {"team": "stone_cold", "values": {"GP": 7, "W": 6, "L": 1, "T": 0, "PTS": 12, "PF": 52, "PA": 33}},
            {"team": "button_pushers", "values": {"GP": 7, "W": 5, "L": 1, "T": 1, "PTS": 11, "PF": 48, "PA": 36}},
            {"team": "hurry_hard", "values": {"GP": 7, "W": 4, "L": 3, "T": 0, "PTS": 8, "PF": 42, "PA": 40}},
            {"team": "free_guards", "values": {"GP": 7, "W": 3, "L": 3, "T": 1, "PTS": 7, "PF": 41, "PA": 43}},
            {"team": "hog_liners", "values": {"GP": 7, "W": 1, "L": 6, "T": 0, "PTS": 2, "PF": 35, "PA": 47}},
            {"team": "takeouts", "values": {"GP": 7, "W": 1, "L": 6, "T": 0, "PTS": 2, "PF": 33, "PA": 52}},
        ],
    },
    "results_header": {"title": "Latest draw", "meta": "Draw 7 · Tue Dec 1"},
    # Legend row above the first card (hammer marker, stolen end, "X Not played").
    "results_legend": ["Hammer in end 1", "Stolen end", "Not played"],
    "bye": None,
    # `hammer` = team with last rock in end 1; `stolen` = ends each team scored
    # without hammer; `blank_ends` = ends where nobody scored; `unplayed_ends`
    # = ends marked X (None in period_scores).  The row order is the mockup's
    # (top row first); curling has no home/away.
    "results": [
        {
            "id": "cu-draw7-a",
            "home": "button_pushers",
            "away": "hurry_hard",
            "designated_home": None,
            "scores": {"button_pushers": 7, "hurry_hard": 5},
            "period_scores": {
                "button_pushers": [0, 0, 1, 1, 0, 3, 0, 2],
                "hurry_hard": [0, 2, 0, 0, 1, 0, 2, 0],
            },
            "status": "Final",
            "tie": False,
            "winner": "button_pushers",
            "date": "Tuesday, Dec 1",
            "time": "6:30 PM",
            "surface": "A",
            "meta": "Sheet A · 6:30 PM",
            "note": None,
            "note_strong": None,
            "note_long": None,
            "link_label": "Game ›",
            "game": "cu-draw7-a",
            "hammer": "hurry_hard",
            "stolen": {"button_pushers": [4], "hurry_hard": []},
            "blank_ends": [1],
            "unplayed_ends": [],
            "shook_hands_after": None,
        },
        {
            "id": "cu-draw7-b",
            "home": "hog_liners",
            "away": "takeouts",
            "designated_home": None,
            "scores": {"hog_liners": 6, "takeouts": 4},
            "period_scores": {
                "hog_liners": [2, 0, 0, 0, 1, 0, 2, 1],
                "takeouts": [0, 1, 0, 1, 0, 2, 0, 0],
            },
            "status": "Final",
            "tie": False,
            "winner": "hog_liners",
            "date": "Tuesday, Dec 1",
            "time": "6:30 PM",
            "surface": "B",
            "meta": "Sheet B · 6:30 PM",
            "note": None,
            "note_strong": None,
            "note_long": None,
            "link_label": "Game ›",
            "game": None,
            "hammer": "hog_liners",
            "stolen": {"hog_liners": [8], "takeouts": [4]},
            "blank_ends": [3],
            "unplayed_ends": [],
            "shook_hands_after": None,
        },
        {
            "id": "cu-draw7-c",
            "home": "stone_cold",
            "away": "free_guards",
            "designated_home": None,
            "scores": {"stone_cold": 8, "free_guards": 3},
            "period_scores": {
                "stone_cold": [0, 2, 2, 0, 3, 1, None, None],
                "free_guards": [1, 0, 0, 2, 0, 0, None, None],
            },
            "status": "Final",
            "tie": False,
            "winner": "stone_cold",
            "date": "Tuesday, Dec 1",
            "time": "8:45 PM",
            "surface": "C",
            "meta": "Sheet C · 8:45 PM · Shook hands after 6",
            "note": None,
            "note_strong": None,
            "note_long": None,
            "link_label": "Game ›",
            "game": None,
            "hammer": "free_guards",
            "stolen": {"stone_cold": [3, 6], "free_guards": []},
            "blank_ends": [],
            "unplayed_ends": [7, 8],
            "shook_hands_after": 6,
        },
    ],
    "featured": None,
    # Curling-Home "Next draw".  Row `time` repeats the group's time (Classic
    # prints it on each row as "6:30"; the sport layout prints it as a group heading).
    "next_day": {
        "eyebrow": "Next draw · Draw 8",
        "label": "Tuesday, Dec 8",
        "label_short": "Tue Dec 8",
        "where": "[Club address]",
        "where_note": None,
        "week_label": None,
        "groups": [
            {
                "time_label": "6:30 PM",
                "rows": [
                    {"surface": "A", "home": "stone_cold", "away": "button_pushers", "time": "6:30 PM"},
                    {"surface": "B", "home": "hurry_hard", "away": "hog_liners", "time": "6:30 PM"},
                ],
            },
            {
                "time_label": "8:45 PM",
                "rows": [
                    {"surface": "C", "home": "free_guards", "away": "takeouts", "time": "8:45 PM"},
                ],
            },
        ],
        "bye": None,
        "foot": "Sheet D: no league game. Every rink plays.",
        "foot_classic": "All times PM. Sheet D: no league game. Every rink plays.",
        "foot_link": None,
    },
    # Curling-Home "Rink leaders" and Classic-Curling-Home "Stolen ends".
    "leaders": {
        "title": "Rink leaders",
        "tiles": [
            {"key": "stolen", "label": "Stolen ends", "value": "9", "name": "Stone Cold", "person": None,
             "team": "stone_cold", "meta": "in 7 games", "edge": None, "only_layouts": ["curling"]},
            {"key": "ends_won", "label": "Ends won", "value": "50%", "name": "Button Pushers", "person": None,
             "team": "button_pushers", "meta": "27 of 54 ends", "edge": None, "only_layouts": None},
            {"key": "big_ends", "label": "Big ends (3+)", "value": "5", "name": "Stone Cold", "person": None,
             "team": "stone_cold", "meta": "in 7 games", "edge": None, "only_layouts": ["classic"]},
        ],
        "lists": [
            {
                "key": "big_ends",
                "title": "Big ends (3 or more)",
                "columns": None,
                "first_row_in_tile": False,
                "only_layouts": ["curling"],
                "note": None,
                "rows": [
                    {"rank": 1, "name": "Stone Cold", "person": None, "team": "stone_cold",
                     "value": "5", "detail": None, "values": None},
                    {"rank": 2, "name": "Button Pushers", "person": None, "team": "button_pushers",
                     "value": "4", "detail": None, "values": None},
                    {"rank": 3, "name": "Hurry Hard", "person": None, "team": "hurry_hard",
                     "value": "3", "detail": None, "values": None},
                ],
            },
            {
                "key": "stolen",
                "title": "Stolen ends",
                "columns": None,
                "first_row_in_tile": False,
                "only_layouts": ["classic"],
                "note": None,
                "unit": "steals",
                "rows": [
                    {"rank": 1, "name": "Stone Cold", "person": None, "team": "stone_cold",
                     "value": "9", "detail": "7 GP · skip Gail R.", "values": None},
                    {"rank": 2, "name": "Button Pushers", "person": None, "team": "button_pushers",
                     "value": "7", "detail": "7 GP · skip Doug H.", "values": None},
                    {"rank": 3, "name": "Free Guards", "person": None, "team": "free_guards",
                     "value": "5", "detail": "7 GP · skip Norm K.", "values": None},
                    {"rank": 4, "name": "Hurry Hard", "person": None, "team": "hurry_hard",
                     "value": "4", "detail": "7 GP · skip Wayne B.", "values": None},
                ],
            },
        ],
        "note": None,
    },
}

# Curling-Game (Button Pushers vs Hurry Hard, Draw 7, Sheet A).
CURLING["game"] = {
    "id": "cu-draw7-a",
    "result": "cu-draw7-a",
    "back_label": "‹ Schedule",
    "nav_current": "Schedule",
    "header": {
        "eyebrow": "Draw 7 · Final",
        "title": "Button Pushers vs Hurry Hard",
        "subline": "Tuesday, Dec 1 · Sheet A · 6:30 PM",
        "venue_line": None,
    },
    "final": {
        "label": None,
        "sub": None,
        "teams": [
            {"team": "button_pushers", "role": None, "record": "5–1–1", "result": "Win",
             "record_text": "Win · now 5–1–1", "score": 7, "winner": True},
            {"team": "hurry_hard", "role": None, "record": "4–3–0", "result": "Loss",
             "record_text": "Loss · now 4–3–0", "score": 5, "winner": False},
        ],
    },
    "line_score": {
        "title": "End by end",
        "meta": "8 ends · no extra end",
        "corner_label": "End",
        "columns": ["1", "2", "3", "4", "5", "6", "7", "8", "Tot"],
        "rows": [
            {"team": "button_pushers", "cells": [0, 0, 1, 1, 0, 3, 0, 2], "total": 7},
            {"team": "hurry_hard", "cells": [0, 2, 0, 0, 1, 0, 2, 0], "total": 5},
        ],
        # Ends in which each team had the hammer (marker under the number).
        # Worked out by the rules (hammer goes to the team that did not score;
        # a blank keeps it); matches the markers in the mockup.
        "hammer_by_end": {"button_pushers": [3, 6, 8], "hurry_hard": [1, 2, 4, 5, 7]},
        "stolen": {"button_pushers": [4], "hurry_hard": []},
        "blank_ends": [1],
        "first_end_hammer": "hurry_hard",
        "note": "Hurry Hard had hammer in the first end.",
        "legend": ["Hammer (last rock)", "Stolen end", "Blank end"],
    },
    "sections": [
        {
            "kind": "numbers",
            "title": "The game in numbers",
            "corner_label": "This game",
            # `emphasis` = team shown in bold in that row (None = neither).
            "rows": [
                {"label": "Ends won", "values": {"button_pushers": "4", "hurry_hard": "3"},
                 "emphasis": "button_pushers", "style": None},
                {"label": "Stolen ends", "values": {"button_pushers": "1", "hurry_hard": "0"},
                 "emphasis": "button_pushers", "style": "stolen"},
                {"label": "Ends with hammer", "values": {"button_pushers": "3", "hurry_hard": "5"},
                 "emphasis": None, "style": None},
                # The mockup printed "2 of 5" for Hurry Hard, but the ends table
                # shows hammer in 5 ends and a score in 3 of them (ends 2, 5, 7).
                # Fixed to "3 of 5".
                {"label": "Scored with hammer", "values": {"button_pushers": "3 of 3", "hurry_hard": "3 of 5"},
                 "emphasis": "button_pushers", "style": None},
                {"label": "Blank ends", "values": {"button_pushers": "0", "hurry_hard": "1"},
                 "emphasis": None, "style": None},
                {"label": "Big ends (3+)", "values": {"button_pushers": "1", "hurry_hard": "0"},
                 "emphasis": "button_pushers", "style": None},
            ],
            "note": "A blank counts to the rink that had hammer and kept it.",
        },
        {
            "kind": "lineups",
            "title": "Lineups",
            "teams": [
                {
                    "team": "button_pushers",
                    "link_label": "Button Pushers Rink ›",
                    "rows": [
                        {"position": "Lead", "player": P(None, "Carol D."), "spare_for": None, "emphasis": False},
                        {"position": "Second", "player": P(None, "Ken W."), "spare_for": None, "emphasis": False},
                        {"position": "Vice", "player": P(None, "Linda F."), "spare_for": None, "emphasis": False},
                        {"position": "Skip", "player": P(None, "Doug H."), "spare_for": None, "emphasis": True},
                    ],
                },
                {
                    "team": "hurry_hard",
                    "link_label": "Hurry Hard Rink ›",
                    "rows": [
                        {"position": "Lead", "player": P(None, "Pat O."), "spare_for": None, "emphasis": False},
                        # Spare badge: Ron M. is a spare for Brian S. (a regular, not in the lineup).
                        {"position": "Second", "player": P(None, "Ron M."), "spare_for": P(None, "Brian S."),
                         "emphasis": False},
                        {"position": "Vice", "player": P(None, "Joanne T."), "spare_for": None, "emphasis": False},
                        {"position": "Skip", "player": P(None, "Wayne B."), "spare_for": None, "emphasis": True},
                    ],
                },
            ],
            "note": "In throwing order: lead first, skip last.",
        },
    ],
    "footnotes": [],
    "calendar": None,
}


# ===========================================================================
# HOCKEY: Northside Old-Timers Hockey
# Copied from Hockey-Home, Classic-Hockey-Home, Hockey-Game.
# ===========================================================================

HOCKEY = {
    "sport": "hockey",
    "name": "Northside Old-Timers Hockey",
    "short_name": "Northside Old-Timers",
    "code": "NOH",
    "tagline": "Hockey · 2026–27",
    "season": "2026–27",
    "nav": NAV,
    "period_word": "Period",
    "period_labels": ["1", "2", "3"],
    "total_label": "T",
    "surface_word": "Pad",
    "venue": "[Arena name]",
    "footer_name": "Northside Old-Timers Hockey",
    "footer_line": "Sunday nights at [Arena name]",
    "footer_links": FOOTER_LINKS,
    "credit": CREDIT,
    # The mockup has no full stop after "[placeholder]" in hockey.
    "points_note": "2 points a win, 1 a tie. Tiebreakers: [placeholder]",
    "labels": {
        "results": "Latest results",
        "next": "Next game night",
        "standings": "Standings",
        "leaders": "Leaders",
        "full_table": "Full table",
        "all_stats": "All stats",
    },
    "layout_labels": {"classic": {"leaders": "Scoring leaders"}},
    # Palette order (slot 1..6).  Codes BLA and WOL are in the Game mockup; the
    # other four are made up for the showcase.
    "teams": [
        _tm("blades", "Blades", "BLA", 1, "red", "#C8102E", "#FF6B7A", "6-1-1"),
        _tm("wolves", "Wolves", "WOL", 2, "blue", "#1D4E89", "#6FA8FF", "5-2-1"),
        _tm("lumberjacks", "Lumberjacks", "LUM", 3, "green", "#2F6B3A", "#4FB164", "4-3-1", False),
        _tm("ice_dogs", "Ice Dogs", "ICE", 4, "teal", "#0E7C8A", "#7FDDE6", "3-4-1", False),
        _tm("grey_owls", "Grey Owls", "OWL", 5, "grey", "#6B7280", "#8E96A3", "2-5-1", False),
        _tm("huskies", "Huskies", "HUS", 6, "brown", "#A8561C", "#F0965A", "1-6-1", False),
    ],
    "standings": {
        "team_label": "Team",
        "team_label_general": "Team",
        "bar": {"basis": "points_of_max", "max": 16},  # 8 GP x 2 points (not shown in a hockey mockup)
        "columns": [
            _col("GP", "GP", "Games played"),
            _col("W", "W", "Wins"),
            _col("L", "L", "Losses"),
            _col("T", "T", "Ties"),
            _col("PTS", "PTS", "Points", True),
            _col("GF", "GF", "Goals for"),
            _col("GA", "GA", "Goals against"),
        ],
        "rows": [
            {"team": "blades", "values": {"GP": 8, "W": 6, "L": 1, "T": 1, "PTS": 13, "GF": 34, "GA": 19}},
            {"team": "wolves", "values": {"GP": 8, "W": 5, "L": 2, "T": 1, "PTS": 11, "GF": 31, "GA": 22}},
            {"team": "lumberjacks", "values": {"GP": 8, "W": 4, "L": 3, "T": 1, "PTS": 9, "GF": 27, "GA": 25}},
            {"team": "ice_dogs", "values": {"GP": 8, "W": 3, "L": 4, "T": 1, "PTS": 7, "GF": 24, "GA": 28}},
            {"team": "grey_owls", "values": {"GP": 8, "W": 2, "L": 5, "T": 1, "PTS": 5, "GF": 21, "GA": 30}},
            {"team": "huskies", "values": {"GP": 8, "W": 1, "L": 6, "T": 1, "PTS": 3, "GF": 19, "GA": 32}},
        ],
    },
    "results_header": {"title": "Latest results", "meta": "Week 8 · Sun Nov 29"},
    "results_legend": [],
    "bye": None,
    # Only the first game has by-period numbers (they come from Hockey-Game).
    # Classic prints the footer as "Final · Game sheet" without the GWG.
    "results": [
        {
            "id": "ho-blades-wolves",
            "home": "blades",
            "away": "wolves",
            "designated_home": None,
            "scores": {"blades": 5, "wolves": 3},
            "period_scores": {"blades": [2, 1, 2], "wolves": [1, 2, 0]},
            "status": "Final",
            "tie": False,
            "winner": "blades",
            "date": "Sunday, Nov 29, 2026",
            "time": "8:00 PM",
            "surface": "1",
            "meta": None,
            "note": "GWG #12 Gord P.",
            "note_strong": "#12 Gord P.",
            "note_long": None,
            "link_label": "Game sheet ›",
            "game": "ho-blades-wolves",
            "gwg": P(12, "Gord P."),
        },
        {
            "id": "ho-icedogs-huskies",
            "home": "ice_dogs",
            "away": "huskies",
            "designated_home": None,
            "scores": {"ice_dogs": 4, "huskies": 2},
            "period_scores": None,
            "status": "Final",
            "tie": False,
            "winner": "ice_dogs",
            "date": "Sunday, Nov 29, 2026",
            "time": None,
            "surface": None,
            "meta": None,
            "note": "GWG #19 Dale M.",
            "note_strong": "#19 Dale M.",
            "note_long": None,
            "link_label": "Game sheet ›",
            "game": None,
            "gwg": P(19, "Dale M."),
        },
        {
            "id": "ho-lumberjacks-owls",
            "home": "lumberjacks",
            "away": "grey_owls",
            "designated_home": None,
            "scores": {"lumberjacks": 3, "grey_owls": 3},
            "period_scores": None,
            "status": "Final",
            "tie": True,
            "winner": None,
            "date": "Sunday, Nov 29, 2026",
            "time": None,
            "surface": None,
            "meta": None,
            "note": "Tie, 1 point each",
            "note_strong": "Tie",
            "note_long": None,
            "link_label": "Game sheet ›",
            "game": None,
            "gwg": None,
        },
    ],
    "featured": None,
    "next_day": {
        "eyebrow": "Next game night",
        "label": "Sunday, Dec 6",
        "label_short": "Sun Dec 6",
        "where": "[Arena name]",
        "where_note": "Pad 1 and Pad 2",
        "week_label": None,
        "groups": [
            {
                "time_label": None,
                "rows": [
                    {"surface": "1", "home": "blades", "away": "ice_dogs", "time": "8:00 PM"},
                    {"surface": "2", "home": "wolves", "away": "huskies", "time": "8:00 PM"},
                    {"surface": "1", "home": "lumberjacks", "away": "grey_owls", "time": "9:15 PM"},
                ],
            }
        ],
        "bye": None,
        "foot": "All six teams play · no bye this week",
        "foot_link": None,
    },
    # Hockey-Home: "Points" table (rank 1 inside the table) + two goalie tiles.
    # Classic-Hockey-Home shows the points rows with "11 G, 7 A" in the detail
    # line and "PTS" under the big number.
    "leaders": {
        "title": "Leaders",
        "tiles": [
            {"key": "gaa", "label": "Goals-against avg", "value": "2.38", "name": "#31 Len T.",
             "person": P(31, "Len T."), "team": "blades", "meta": "Blades · 19 GA in 8 GP",
             "edge": "accent", "only_layouts": None, "group": "Goalies"},
            {"key": "shutouts", "label": "Shutouts", "value": "2", "name": "#30 Stan V.",
             "person": P(30, "Stan V."), "team": "ice_dogs", "meta": "Ice Dogs · 8 GP",
             "edge": "hot", "only_layouts": None, "group": "Goalies"},
        ],
        "lists": [
            {
                "key": "points",
                "title": "Points",
                "columns": [_col("G", "G", "Goals"), _col("A", "A", "Assists"), _col("PTS", "PTS", "Points", True)],
                "first_row_in_tile": False,
                "only_layouts": None,
                "note": None,
                "unit": "PTS",
                "rows": [
                    {"rank": 1, "name": "#12 Gord P.", "person": P(12, "Gord P."), "team": "blades",
                     "value": "18", "detail": "8 GP", "values": {"G": 11, "A": 7, "PTS": 18}},
                    {"rank": 2, "name": "#9 Wayne K.", "person": P(9, "Wayne K."), "team": "wolves",
                     "value": "17", "detail": "8 GP", "values": {"G": 9, "A": 8, "PTS": 17}},
                    {"rank": 3, "name": "#27 Rick D.", "person": P(27, "Rick D."), "team": "lumberjacks",
                     "value": "15", "detail": "8 GP", "values": {"G": 6, "A": 9, "PTS": 15}},
                    {"rank": 4, "name": "#4 Barry S.", "person": P(4, "Barry S."), "team": "blades",
                     "value": "14", "detail": "8 GP", "values": {"G": 5, "A": 9, "PTS": 14}},
                    {"rank": 5, "name": "#19 Dale M.", "person": P(19, "Dale M."), "team": "ice_dogs",
                     "value": "13", "detail": "7 GP", "values": {"G": 8, "A": 5, "PTS": 13}},
                ],
            }
        ],
        "note": "Goalies need 4 games played to rank.",
    },
}

# Hockey-Game (Blades vs Wolves, Week 8).  Scores in the scoring summary are
# written "Blades first" (the first-listed team).
HOCKEY["game"] = {
    "id": "ho-blades-wolves",
    "result": "ho-blades-wolves",
    "back_label": "‹ Schedule",
    "nav_current": "Schedule",
    "header": {
        "eyebrow": None,
        "title": "Blades vs Wolves",
        "subline": "Sunday, Nov 29, 2026 · 8:00 PM",
        "venue_line": "[Arena name] · Pad 1 · Week 8",
    },
    "final": {
        "label": "Final",
        "sub": None,
        "teams": [
            {"team": "blades", "role": None, "record": "6-1-1", "result": "Win",
             "record_text": "6-1-1 · Win", "score": 5, "winner": True},
            {"team": "wolves", "role": None, "record": "5-2-1", "result": "Loss",
             "record_text": "5-2-1 · Loss", "score": 3, "winner": False},
        ],
    },
    "line_score": {
        "title": None,
        "meta": None,
        "corner_label": "Period",
        "columns": ["1", "2", "3", "T"],
        "rows": [
            {"team": "blades", "cells": [2, 1, 2], "total": 5},
            {"team": "wolves", "cells": [1, 2, 0], "total": 3},
        ],
        # Line under the table: goalies and penalty minutes.
        "foot_goalies": [P(31, "Len T."), P(1, "Murray B.")],
        "foot_pim": {"blades": 4, "wolves": 4},
    },
    "sections": [
        {
            "kind": "scoring",
            "title": "Scoring",
            "periods": [
                {
                    "label": "1st period",
                    "tally": {"blades": 2, "wolves": 1},
                    "goals": [
                        {"time": "4:12", "team": "blades", "scorer": P(12, "Gord P."),
                         "assists": [P(4, "Barry S."), P(17, "Ken L.")], "score": [1, 0], "gwg": False},
                        {"time": "9:38", "team": "wolves", "scorer": P(9, "Wayne K."),
                         "assists": [P(14, "Rod B.")], "score": [1, 1], "gwg": False},
                        {"time": "13:05", "team": "blades", "scorer": P(17, "Ken L."),
                         "assists": [P(12, "Gord P.")], "score": [2, 1], "gwg": False},
                    ],
                },
                {
                    "label": "2nd period",
                    "tally": {"blades": 1, "wolves": 2},
                    "goals": [
                        {"time": "2:47", "team": "wolves", "scorer": P(14, "Rod B."),
                         "assists": [P(9, "Wayne K."), P(2, "Phil A.")], "score": [2, 2], "gwg": False},
                        {"time": "7:20", "team": "blades", "scorer": P(8, "Doug H."),
                         "assists": [P(22, "Al F.")], "score": [3, 2], "gwg": False},
                        {"time": "11:54", "team": "wolves", "scorer": P(9, "Wayne K."),
                         "assists": [], "score": [3, 3], "gwg": False},  # Unassisted
                    ],
                },
                {
                    "label": "3rd period",
                    "tally": {"blades": 2, "wolves": 0},
                    "goals": [
                        {"time": "5:31", "team": "blades", "scorer": P(12, "Gord P."),
                         "assists": [P(4, "Barry S.")], "score": [4, 3], "gwg": True},
                        {"time": "12:09", "team": "blades", "scorer": P(4, "Barry S."),
                         "assists": [P(12, "Gord P."), P(6, "Terry W.")], "score": [5, 3], "gwg": False},
                    ],
                },
            ],
            "note": "Score shown Blades first. Times as written on the game sheet.",
        },
        {
            "kind": "penalties",
            "title": "Penalties",
            "columns": ["Per", "Time", "Player", "Infraction", "Min"],
            # Team of each penalty is the colour dot next to the player; taken
            # from the skaters tables below.
            "rows": [
                {"period": 1, "time": "12:15", "team": "wolves", "player": P(21, "Bob C."),
                 "infraction": "Tripping", "minutes": 2},
                {"period": 2, "time": "9:02", "team": "blades", "player": P(22, "Al F."),
                 "infraction": "Hooking", "minutes": 2},
                {"period": 3, "time": "8:44", "team": "wolves", "player": P(11, "Gary N."),
                 "infraction": "Slashing", "minutes": 2},
                {"period": 3, "time": "14:10", "team": "blades", "player": P(8, "Doug H."),
                 "infraction": "Body contact", "minutes": 2},
            ],
            "legend_teams": ["blades", "wolves"],
        },
        {
            "kind": "goalies",
            "title": "Goalies",
            "columns": ["Goalie", "Team", "Result", "GA"],
            "rows": [
                {"player": P(31, "Len T."), "team": "blades", "result": "W", "ga": 3},
                {"player": P(1, "Murray B."), "team": "wolves", "result": "L", "ga": 5},
            ],
            "note": "Both goalies played the full game.",
        },
        {
            "kind": "skaters",
            "title": "Skaters",
            "intro": "Players with a goal, assist or penalty.",
            "columns": [_col("G", "G", "Goals"), _col("A", "A", "Assists"), _col("PTS", "PTS", "Points", True),
                        _col("PIM", "PIM", "Penalty minutes")],
            "teams": [
                {
                    "team": "blades",
                    "rows": [
                        {"player": P(12, "Gord P."), "g": 2, "a": 2, "pts": 4, "pim": 0},
                        {"player": P(4, "Barry S."), "g": 1, "a": 2, "pts": 3, "pim": 0},
                        {"player": P(17, "Ken L."), "g": 1, "a": 1, "pts": 2, "pim": 0},
                        {"player": P(8, "Doug H."), "g": 1, "a": 0, "pts": 1, "pim": 2},
                        {"player": P(22, "Al F."), "g": 0, "a": 1, "pts": 1, "pim": 2},
                        {"player": P(6, "Terry W."), "g": 0, "a": 1, "pts": 1, "pim": 0},
                    ],
                    "total": {"g": 5, "a": 7, "pts": 12, "pim": 4},
                },
                {
                    "team": "wolves",
                    "rows": [
                        {"player": P(9, "Wayne K."), "g": 2, "a": 1, "pts": 3, "pim": 0},
                        {"player": P(14, "Rod B."), "g": 1, "a": 1, "pts": 2, "pim": 0},
                        {"player": P(2, "Phil A."), "g": 0, "a": 1, "pts": 1, "pim": 0},
                        {"player": P(21, "Bob C."), "g": 0, "a": 0, "pts": 0, "pim": 2},
                        {"player": P(11, "Gary N."), "g": 0, "a": 0, "pts": 0, "pim": 2},
                    ],
                    "total": {"g": 3, "a": 3, "pts": 6, "pim": 4},
                },
            ],
        },
    ],
    "footnotes": [],
    "foot_link": "Full rosters on the team pages ›",
    "calendar": None,
}


# ===========================================================================
# SLO-PITCH: Maple Park Slo-Pitch
# Copied from Slopitch-Home, Slopitch-Game, Scoreboard-Slopitch-Home.
# ===========================================================================

SLOPITCH = {
    "sport": "slopitch",
    "name": "Maple Park Slo-Pitch",
    "short_name": "Maple Park Slo-Pitch",
    "code": "MP",
    "tagline": "55+ · 2027 season",
    "season": "2027 season",
    "nav": NAV,
    "period_word": "Inning",
    "period_labels": ["1", "2", "3", "4", "5", "6", "7"],
    "total_label": "R",
    "surface_word": "Diamond",
    "venue": "[Park name]",
    "footer_name": "Maple Park Slo-Pitch · 55+",
    "footer_line": None,
    "footer_links": FOOTER_LINKS,
    "credit": CREDIT,
    "points_note": "2 points a win, 1 a tie. Tiebreakers: [placeholder].",
    "run_limit": 5,
    "last_inning_open": True,  # Scoreboard: "7th inning open"
    "labels": {
        "results": "Latest results",
        "next": "Next game day",
        "standings": "Standings",
        "leaders": "Leaders",
        "full_table": "Full table",
        "all_stats": "All stats",
    },
    "layout_labels": {
        "scoreboard": {
            "results": "Game of the week",
            "next": "Next up",
            "standings": "The race",
            "leaders": "Hitting",
            "full_table": "Full standings with RF and RA",
            "all_stats": "All player stats",
        },
    },
    # Palette order (slot 1..6).  Codes are the Scoreboard ticker's.
    "teams": [
        _tm("sluggers", "Sluggers", "SLG", 1, "red", "#B23A2E", "#F27463", "5-1-0"),
        _tm("mudcats", "Mudcats", "MUD", 2, "brown", "#7A5A3A", "#A8825A", "2-3-1"),
        _tm("dugout_dogs", "Dugout Dogs", "DDG", 3, "blue", "#2F5DA8", "#6E98EA", "3-2-1"),
        _tm("line_drives", "Line Drives", "LND", 4, "gold", "#C98A12", "#F0C04A", "2-3-1"),
        _tm("long_balls", "Long Balls", "LGB", 5, "purple", "#5C3F8F", "#B9A3F0", "4-2-0"),
        _tm("bunters", "Bunters", "BUN", 6, "teal", "#2B8C8C", "#5CC7C2", "0-5-1"),
    ],
    "standings": {
        "team_label": "Team",
        "team_label_general": "Team",
        "bar": {"basis": "points_of_max", "max": 12},  # Scoreboard: "points out of 12 possible"
        "columns": [
            _col("GP", "GP", "Games played"),
            _col("W", "W", "Wins"),
            _col("L", "L", "Losses"),
            _col("T", "T", "Ties"),
            _col("PTS", "PTS", "Points", True),
            _col("RF", "RF", "Runs for"),
            _col("RA", "RA", "Runs against"),
        ],
        "rows": [
            {"team": "sluggers", "values": {"GP": 6, "W": 5, "L": 1, "T": 0, "PTS": 10, "RF": 72, "RA": 48}},
            {"team": "long_balls", "values": {"GP": 6, "W": 4, "L": 2, "T": 0, "PTS": 8, "RF": 66, "RA": 50}},
            {"team": "dugout_dogs", "values": {"GP": 6, "W": 3, "L": 2, "T": 1, "PTS": 7, "RF": 58, "RA": 55}},
            {"team": "line_drives", "values": {"GP": 6, "W": 2, "L": 3, "T": 1, "PTS": 5, "RF": 54, "RA": 58}},
            {"team": "mudcats", "values": {"GP": 6, "W": 2, "L": 3, "T": 1, "PTS": 5, "RF": 55, "RA": 63}},
            {"team": "bunters", "values": {"GP": 6, "W": 0, "L": 5, "T": 1, "PTS": 1, "RF": 41, "RA": 72}},
        ],
    },
    "results_header": {"title": "Latest results", "meta": "Week 6 · Wed Jun 16"},
    "results_legend": ["5 = inning ended at the 5-run limit. X = not needed."],
    "bye": None,
    # Top row first.  `hits` = the H column; `limit_innings` = innings that
    # ended at the 5-run limit (boxed/circled 5); `x_innings` = innings not
    # played ("X").  In game 1 the Game mockup says Mudcats visit, Sluggers are home.
    "results": [
        {
            "id": "sp-mudcats-sluggers",
            "home": "mudcats",
            "away": "sluggers",
            "designated_home": "sluggers",
            "scores": {"mudcats": 11, "sluggers": 14},
            "period_scores": {
                "mudcats": [2, 0, 5, 1, 0, 3, 0],
                "sluggers": [1, 5, 0, 3, 5, 0, None],
            },
            "hits": {"mudcats": 15, "sluggers": 18},
            "limit_innings": {"mudcats": [3], "sluggers": [2, 5]},
            "x_innings": {"mudcats": [], "sluggers": [7]},
            "status": "Final",
            "tie": False,
            "winner": "sluggers",
            "date": "Wed Jun 16, 2027",
            "time": "6:30 PM",
            "surface": "1",
            "meta": "Diamond 1",
            "note": "Top bat: Gary T. 3 for 4",
            "note_strong": "Gary T.",
            "note_long": "Top bat: Gary T. 3 for 4, 2 R · Ron B. HR, 3 RBI",  # Scoreboard
            "link_label": "Box score ›",
            "game": "sp-mudcats-sluggers",
        },
        {
            "id": "sp-bunters-longballs",
            "home": "bunters",
            "away": "long_balls",
            "designated_home": None,
            "scores": {"bunters": 6, "long_balls": 10},
            "period_scores": {
                "bunters": [0, 2, 1, 0, 3, 0, 0],
                "long_balls": [3, 0, 5, 0, 2, 0, None],
            },
            "hits": {"bunters": 11, "long_balls": 14},
            "limit_innings": {"bunters": [], "long_balls": [3]},
            "x_innings": {"bunters": [], "long_balls": [7]},
            "status": "Final",
            "tie": False,
            "winner": "long_balls",
            "date": "Wed Jun 16, 2027",
            "time": None,
            "surface": "2",
            "meta": "Diamond 2",
            "note": "Top bat: Rita C. 3 for 3, 3 RBI",
            "note_strong": "Rita C.",
            "note_long": None,
            "link_label": "Box score ›",
            "game": None,
        },
        {
            "id": "sp-linedrives-dugoutdogs",
            "home": "line_drives",
            "away": "dugout_dogs",
            "designated_home": None,
            "scores": {"line_drives": 8, "dugout_dogs": 8},
            "period_scores": {
                "line_drives": [1, 0, 2, 4, 0, 1, 0],
                "dugout_dogs": [0, 3, 0, 1, 2, 0, 2],
            },
            "hits": {"line_drives": 13, "dugout_dogs": 12},
            "limit_innings": {"line_drives": [], "dugout_dogs": []},
            "x_innings": {"line_drives": [], "dugout_dogs": []},
            "status": "Final",
            "tie": True,
            "winner": None,
            "date": "Wed Jun 16, 2027",
            "time": None,
            "surface": "3",
            "meta": "Diamond 3",
            "note": "Top bat: Hank W. 3 for 4, 2 RBI",
            "note_strong": "Hank W.",
            "note_long": None,
            "link_label": "Box score ›",
            "game": None,
        },
    ],
    # Scoreboard "Game of the week".
    "featured": {"result": "sp-mudcats-sluggers", "label": "Game of the week", "date": "Final · Jun 16"},
    "next_day": {
        "eyebrow": "Next game day",
        "label": "Wednesday, Jun 23",
        "label_short": "Wednesday, Jun 23",
        "where": "[Park name]",
        "where_note": None,
        "week_label": None,
        "groups": [
            {
                "time_label": None,
                "rows": [
                    {"surface": "1", "home": "long_balls", "away": "sluggers", "time": "6:30 PM"},
                    {"surface": "2", "home": "dugout_dogs", "away": "mudcats", "time": "6:30 PM"},
                    {"surface": "3", "home": "line_drives", "away": "bunters", "time": "7:45 PM"},
                ],
            }
        ],
        "bye": None,
        "foot": "All six teams play. No bye this week.",
        "foot_scoreboard": "All times PM · D = Diamond · No bye this week",
        "foot_link": None,
    },
    # Slopitch-Home leaders; Scoreboard shows 3 rows of each list (rank 1 included).
    "leaders": {
        "title": "Leaders",
        "tiles": [
            {"key": "avg", "label": "Batting avg", "value": ".640", "name": "Gary T.",
             "person": P(None, "Gary T."), "team": "sluggers", "meta": "Sluggers · 16 for 25",
             "edge": "hot", "only_layouts": None},
            {"key": "hr", "label": "Home runs", "value": "4", "name": "Phil G.",
             "person": P(None, "Phil G."), "team": "mudcats", "meta": "Mudcats · 6 games",
             "edge": "accent", "only_layouts": None},
        ],
        "lists": [
            {
                "key": "avg",
                "title": "Batting average · next best",
                "title_scoreboard": "Batting average · min. 15 AB",
                "columns": None,
                "first_row_in_tile": True,
                "only_layouts": None,
                "note": "Minimum 15 at-bats to qualify for average.",
                "rows": [
                    {"rank": 1, "name": "Gary T.", "person": P(None, "Gary T."), "team": "sluggers",
                     "value": ".640", "detail": "16 for 25", "values": None},
                    {"rank": 2, "name": "Norm W.", "person": P(None, "Norm W."), "team": "mudcats",
                     "value": ".609", "detail": "14 for 23", "values": None},
                    {"rank": 3, "name": "Ron B.", "person": P(None, "Ron B."), "team": "sluggers",
                     "value": ".583", "detail": "14 for 24", "values": None},
                    {"rank": 4, "name": "Rita C.", "person": P(None, "Rita C."), "team": "long_balls",
                     "value": ".571", "detail": "12 for 21", "values": None},
                ],
            },
            {
                "key": "hr",
                "title": "Home runs",
                "columns": None,
                "first_row_in_tile": True,
                "only_layouts": ["scoreboard"],
                "note": None,
                "rows": [
                    {"rank": 1, "name": "Phil G.", "person": P(None, "Phil G."), "team": "mudcats",
                     "value": "4", "detail": "6 games", "values": None},
                    {"rank": 2, "name": "Ron B.", "person": P(None, "Ron B."), "team": "sluggers",
                     "value": "3", "detail": "6 games", "values": None},
                    {"rank": 3, "name": "Dave K.", "person": P(None, "Dave K."), "team": "sluggers",
                     "value": "3", "detail": "6 games", "values": None},
                ],
            },
        ],
        "note": None,
    },
}

# Slopitch-Game (Mudcats at Sluggers, Week 6).
SLOPITCH["game"] = {
    "id": "sp-mudcats-sluggers",
    "result": "sp-mudcats-sluggers",
    "back_label": "‹ Schedule",
    "nav_current": "Schedule",
    "header": {
        "eyebrow": "Week 6 · Final",
        "title": "Mudcats at Sluggers",
        "subline": "Wed Jun 16, 2027 · 6:30 PM",
        "venue_line": "Diamond 1 · [Park name]",
    },
    "final": {
        "label": None,
        "sub": None,
        "teams": [
            {"team": "mudcats", "role": "Visitors", "record": "2-3-1", "result": None,
             "record_text": "Visitors · 2-3-1", "score": 11, "winner": False},
            {"team": "sluggers", "role": "Home", "record": "5-1-0", "result": "WIN",
             "record_text": "Home · 5-1-0", "score": 14, "winner": True},
        ],
    },
    "line_score": {
        "title": "Line score",
        "meta": None,
        "corner_label": "Inning",
        "columns": ["1", "2", "3", "4", "5", "6", "7 open", "R", "H"],
        "rows": [
            {"team": "mudcats", "cells": [2, 0, 5, 1, 0, 3, 0], "total": 11, "hits": 15},
            {"team": "sluggers", "cells": [1, 5, 0, 3, 5, 0, None], "total": 14, "hits": 18},
        ],
        "limit_innings": {"mudcats": [3], "sluggers": [2, 5]},
        "x_innings": {"mudcats": [], "sluggers": [7]},
        "notes": [
            {"mark": "5", "kind": "limit",
             "text": "Circled: the inning ended at the 5-run limit. The 7th is open (no limit)."},
            {"mark": "X", "kind": "x",
             "text": "Sluggers led after the top of the 7th, so they didn't bat."},
        ],
    },
    "sections": [
        {
            "kind": "facts",
            "title": None,
            "rows": [
                {"label": "Home runs",
                 "groups": [
                     {"team": "sluggers", "players": [P(None, "Ron B."), P(None, "Dave K.")]},
                     {"team": "mudcats", "players": [P(None, "Phil G.")]},
                 ]},
                {"label": "3 hits",
                 "groups": [
                     {"team": "sluggers", "players": [P(None, "Gary T."), P(None, "Ron B.")]},
                     {"team": "mudcats", "players": [P(None, "Norm W.")]},
                 ]},
                {"label": "Limit innings",
                 "limit": [
                     {"team": "sluggers", "count": 2, "innings": ["2nd", "5th"]},
                     {"team": "mudcats", "count": 1, "innings": ["3rd"]},
                 ]},
            ],
        },
        {
            "kind": "batting",
            "title": "Mudcats batting",
            "team": "mudcats",
            "order_label": "#",
            "player_label": "Batter",
            "columns": [_col("AB", "AB", "At bats"), _col("R", "R", "Runs"), _col("H", "H", "Hits"),
                        _col("RBI", "RBI", "Runs batted in"), _col("HR", "HR", "Home runs")],
            "rows": [
                {"order": 1, "player": P(None, "Norm W."), "ab": 4, "r": 2, "h": 3, "rbi": 0, "hr": 0},
                {"order": 2, "player": P(None, "Sheila R."), "ab": 4, "r": 1, "h": 2, "rbi": 1, "hr": 0},
                {"order": 3, "player": P(None, "Phil G."), "ab": 4, "r": 2, "h": 2, "rbi": 3, "hr": 1},
                {"order": 4, "player": P(None, "Doug E."), "ab": 4, "r": 1, "h": 2, "rbi": 2, "hr": 0},
                {"order": 5, "player": P(None, "Pat O."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 6, "player": P(None, "Ken J."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 7, "player": P(None, "Marg L."), "ab": 3, "r": 1, "h": 1, "rbi": 0, "hr": 0},
                {"order": 8, "player": P(None, "Brian C."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 9, "player": P(None, "Elaine V."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 10, "player": P(None, "Stan Z."), "ab": 3, "r": 0, "h": 1, "rbi": 0, "hr": 0},
            ],
            "totals": {"label": "Totals", "ab": 34, "r": 11, "h": 15, "rbi": 10, "hr": 1},
        },
        {
            "kind": "batting",
            "title": "Sluggers batting",
            "team": "sluggers",
            "order_label": "#",
            "player_label": "Batter",
            "columns": [_col("AB", "AB", "At bats"), _col("R", "R", "Runs"), _col("H", "H", "Hits"),
                        _col("RBI", "RBI", "Runs batted in"), _col("HR", "HR", "Home runs")],
            "rows": [
                {"order": 1, "player": P(None, "Gary T."), "ab": 4, "r": 2, "h": 3, "rbi": 0, "hr": 0},
                {"order": 2, "player": P(None, "Linda M."), "ab": 4, "r": 2, "h": 2, "rbi": 1, "hr": 0},
                {"order": 3, "player": P(None, "Ron B."), "ab": 4, "r": 2, "h": 3, "rbi": 3, "hr": 1},
                {"order": 4, "player": P(None, "Dave K."), "ab": 3, "r": 2, "h": 2, "rbi": 4, "hr": 1},
                {"order": 5, "player": P(None, "Bev S."), "ab": 3, "r": 1, "h": 2, "rbi": 2, "hr": 0},
                {"order": 6, "player": P(None, "Wayne H."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 7, "player": P(None, "Carol D."), "ab": 3, "r": 1, "h": 2, "rbi": 1, "hr": 0},
                {"order": 8, "player": P(None, "Ted F."), "ab": 3, "r": 1, "h": 1, "rbi": 0, "hr": 0},
                {"order": 9, "player": P(None, "Joan P."), "ab": 3, "r": 1, "h": 1, "rbi": 1, "hr": 0},
                {"order": 10, "player": P(None, "Murray L."), "ab": 3, "r": 1, "h": 1, "rbi": 0, "hr": 0},
            ],
            "totals": {"label": "Totals", "ab": 33, "r": 14, "h": 18, "rbi": 13, "hr": 2},
        },
    ],
    "footnotes": ["# = batting order from the score sheet. Swipe the table sideways on a small phone."],
    "calendar": None,
}


LEAGUES = {
    "basketball": BASKETBALL,
    "curling": CURLING,
    "hockey": HOCKEY,
    "slopitch": SLOPITCH,
}


# ---------------------------------------------------------------------------
# 5. Self-check:  python3 -m scripts.design_system.sample
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[A-Z][A-Za-z'\-]+ [A-Z]\.$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COUNT_COLS = ("GP", "W", "L", "T")


def _fail(msg):
    raise AssertionError(msg)


def _people(obj, found):
    """Collect every person dict inside obj."""
    if isinstance(obj, dict):
        if set(obj) == {"number", "name", "label"}:
            found.append(obj)
        else:
            for v in obj.values():
                _people(v, found)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _people(v, found)


def _check_people(sport, league):
    people = []
    _people(league, people)
    for p in people:
        if not _NAME_RE.match(p["name"]):
            _fail("%s: person name not 'First L.': %r" % (sport, p["name"]))
        expect = ("#%s %s" % (p["number"], p["name"])) if p["number"] else p["name"]
        if p["label"] != expect:
            _fail("%s: bad label %r (want %r)" % (sport, p["label"], expect))
    return len(people)


def _check_league(sport, league):
    ids = [t["id"] for t in league["teams"]]
    if len(set(ids)) != len(ids):
        _fail("%s: duplicate team ids" % sport)
    slots = sorted(t["slot"] for t in league["teams"])
    if slots != list(range(1, len(ids) + 1)):
        _fail("%s: slots must be 1..%d, got %s" % (sport, len(ids), slots))
    codes = [t["code"] for t in league["teams"]]
    if len(set(codes)) != len(codes):
        _fail("%s: duplicate team codes" % sport)
    idset = set(ids)

    def ref(tid, where):
        if tid not in idset:
            _fail("%s: unknown team %r in %s" % (sport, tid, where))

    # standings: every column, W+L+T=GP, points rule, for = against, record string
    st = league["standings"]
    keys = [c["key"] for c in st["columns"]]
    if len(st["rows"]) != len(ids):
        _fail("%s: standings must list every team once" % sport)
    seen = []
    for row in st["rows"]:
        ref(row["team"], "standings")
        seen.append(row["team"])
        v = row["values"]
        for k in keys:
            if k not in v:
                _fail("%s: standings row %s lacks column %s" % (sport, row["team"], k))
        if set(v) != set(keys):
            _fail("%s: standings row %s has extra columns" % (sport, row["team"]))
        if all(k in v for k in ("W", "L", "T", "GP")) and v["W"] + v["L"] + v["T"] != v["GP"]:
            _fail("%s: W+L+T != GP for %s" % (sport, row["team"]))
        if sport != "basketball" and v["PTS"] != 2 * v["W"] + v["T"]:
            _fail("%s: PTS != 2W+T for %s" % (sport, row["team"]))
        rec = re.split("[-–]", team(sport, row["team"])["record"])
        want = [v["W"], v["L"]] + ([v["T"]] if "T" in v else [])
        if [int(x) for x in rec] != want:
            _fail("%s: record %r != standings %s for %s" % (sport, rec, want, row["team"]))
    if sorted(seen) != sorted(ids):
        _fail("%s: standings teams differ from teams list" % sport)
    for_k, against_k = {"curling": ("PF", "PA"), "hockey": ("GF", "GA"), "slopitch": ("RF", "RA")}.get(
        sport, (None, None))
    if for_k:
        if sum(r["values"][for_k] for r in st["rows"]) != sum(r["values"][against_k] for r in st["rows"]):
            _fail("%s: %s total != %s total" % (sport, for_k, against_k))
    if sum(r["values"]["W"] for r in st["rows"]) != sum(r["values"]["L"] for r in st["rows"]):
        _fail("%s: total wins != total losses" % sport)
    if sport == "basketball":
        if sum(int(r["values"]["DIFF"].replace("−", "-")) for r in st["rows"]) != 0:
            _fail("basketball: DIFF column does not sum to 0")
        top = st["rows"][0]["values"]
        for r in st["rows"]:
            v = r["values"]
            if "%.3f" % (v["W"] / (v["W"] + v["L"])) != ("%.3f" % float(v["PCT"])):
                _fail("basketball: PCT wrong for %s" % r["team"])
            gb = ((top["W"] - v["W"]) + (v["L"] - top["L"])) / 2
            want_gb = "—" if gb == 0 else ("%g" % gb)
            if v["GB"] != want_gb:
                _fail("basketball: GB wrong for %s: %s != %s" % (r["team"], v["GB"], want_gb))

    # results
    n = len(league["period_labels"])
    rids = set()
    for r in league["results"]:
        rids.add(r["id"])
        ref(r["home"], "result " + r["id"])
        ref(r["away"], "result " + r["id"])
        if r["home"] == r["away"]:
            _fail("%s: result plays itself" % r["id"])
        if r["designated_home"] not in (None, r["home"], r["away"]):
            _fail("%s: designated_home not in game" % r["id"])
        if set(r["scores"]) != {r["home"], r["away"]}:
            _fail("%s: scores keys" % r["id"])
        a, b = r["home"], r["away"]
        want_win = None if r["scores"][a] == r["scores"][b] else (a if r["scores"][a] > r["scores"][b] else b)
        if r["winner"] != want_win:
            _fail("%s: winner should be %s" % (r["id"], want_win))
        if r["tie"] != (want_win is None):
            _fail("%s: tie flag" % r["id"])
        ps = r["period_scores"]
        if ps is not None:
            if set(ps) != {a, b}:
                _fail("%s: period_scores keys" % r["id"])
            for tid, cells in ps.items():
                if len(cells) != n:
                    _fail("%s: %s has %d periods, want %d" % (r["id"], tid, len(cells), n))
                if sum(c for c in cells if c is not None) != r["scores"][tid]:
                    _fail("%s: %s period scores sum to %s, final is %s" % (
                        r["id"], tid, sum(c for c in cells if c is not None), r["scores"][tid]))
        if r["game"] is not None and r["game"] != league["game"]["id"]:
            _fail("%s: game id does not match the league's game" % r["id"])
        if sport == "curling":
            _check_curling_result(r)
        if sport == "slopitch":
            for tid in (a, b):
                for key in ("limit_innings", "x_innings"):
                    for inn in r[key][tid]:
                        if not 1 <= inn <= n:
                            _fail("%s: bad inning %s" % (r["id"], inn))
                for inn in r["limit_innings"][tid]:
                    if ps[tid][inn - 1] != league["run_limit"]:
                        _fail("%s: limit inning %d is not %d runs" % (r["id"], inn, league["run_limit"]))
                for inn in r["x_innings"][tid]:
                    if ps[tid][inn - 1] is not None:
                        _fail("%s: X inning should be None" % r["id"])
            if set(r["hits"]) != {a, b}:
                _fail("%s: hits keys" % r["id"])
    if league["bye"] is not None:
        ref(league["bye"], "bye")
    if league["featured"] and league["featured"]["result"] not in rids:
        _fail("%s: featured result missing" % sport)

    # next day
    nd = league["next_day"]
    playing = []
    for g in nd["groups"]:
        for row in g["rows"]:
            ref(row["home"], "next_day")
            ref(row["away"], "next_day")
            playing += [row["home"], row["away"]]
            if g["time_label"] is not None and row["time"] != g["time_label"]:
                _fail("%s: row time differs from its group's time" % sport)
    if nd["bye"]:
        ref(nd["bye"], "next_day.bye")
        playing.append(nd["bye"])
    if len(set(playing)) != len(playing):
        _fail("%s: a team appears twice in next_day" % sport)
    if set(playing) != idset and sport in ("hockey", "slopitch", "basketball"):
        _fail("%s: next_day should account for every team (play or bye)" % sport)

    # leaders
    ld = league["leaders"]
    for t in ld["tiles"]:
        if t["team"]:
            ref(t["team"], "leaders tile")
    for lst in ld["lists"]:
        ranks = [row["rank"] for row in lst["rows"]]
        if ranks != sorted(ranks):
            _fail("%s: leaders list %s ranks out of order" % (sport, lst["key"]))
        for row in lst["rows"]:
            ref(row["team"], "leaders list")
            if lst["columns"]:
                if set(row["values"]) != {c["key"] for c in lst["columns"]}:
                    _fail("%s: leaders row columns" % sport)
        if lst["first_row_in_tile"]:
            tile = [t for t in ld["tiles"] if t["key"] == lst["key"]]
            if tile and tile[0]["value"] != lst["rows"][0]["value"]:
                _fail("%s: tile %s differs from rank 1 of its list" % (sport, lst["key"]))
    if sport == "hockey":
        for row in ld["lists"][0]["rows"]:
            v = row["values"]
            if v["G"] + v["A"] != v["PTS"] or str(v["PTS"]) != row["value"]:
                _fail("hockey: leaders G+A != PTS for %s" % row["name"])

    return league


def _check_curling_result(r):
    """Replay the hammer rule and compare with `stolen`, `blank_ends`, `hammer`."""
    a, b = r["home"], r["away"]
    ps = r["period_scores"]
    hammer = r["hammer"]
    if hammer not in (a, b):
        _fail("%s: hammer team not in game" % r["id"])
    n = len(ps[a])
    stolen = {a: [], b: []}
    blank = []
    unplayed = [i + 1 for i in range(n) if ps[a][i] is None]
    if unplayed != [i + 1 for i in range(n) if ps[b][i] is None] or unplayed != r["unplayed_ends"]:
        _fail("%s: unplayed ends disagree" % r["id"])
    if r["shook_hands_after"] is not None and unplayed != list(range(r["shook_hands_after"] + 1, n + 1)):
        _fail("%s: shook_hands_after disagrees with unplayed ends" % r["id"])
    for i in range(n):
        if ps[a][i] is None:
            continue
        other = b if hammer == a else a
        sa, sb = ps[a][i], ps[b][i]
        if sa and sb:
            _fail("%s: both teams scored in end %d" % (r["id"], i + 1))
        if sa == 0 and sb == 0:
            blank.append(i + 1)  # hammer is kept
        else:
            scorer = a if sa else b
            if scorer == hammer:
                hammer = other  # hammer scored: gives it up
            else:
                stolen[scorer].append(i + 1)
                # the non-scoring team (the one with hammer) keeps it
    if stolen != r["stolen"]:
        _fail("%s: stolen ends %s != computed %s" % (r["id"], r["stolen"], stolen))
    if blank != r["blank_ends"]:
        _fail("%s: blank ends %s != computed %s" % (r["id"], r["blank_ends"], blank))


def _check_curling_game(league):
    g = league["game"]
    r = [x for x in league["results"] if x["id"] == g["result"]][0]
    a, b = r["home"], r["away"]
    ls = g["line_score"]
    for row in ls["rows"]:
        if row["cells"] != r["period_scores"][row["team"]] or row["total"] != r["scores"][row["team"]]:
            _fail("curling game: line score differs from the result")
    # hammer by end
    ps = r["period_scores"]
    hb = {a: [], b: []}
    ham = r["hammer"]
    for i in range(len(ps[a])):
        hb[ham].append(i + 1)
        sa, sb = ps[a][i], ps[b][i]
        if sa or sb:
            scorer = a if sa else b
            if scorer == ham:
                ham = b if ham == a else a
    if hb != ls["hammer_by_end"]:
        _fail("curling game: hammer_by_end %s != computed %s" % (ls["hammer_by_end"], hb))
    # the game in numbers
    won = {a: 0, b: 0}
    big = {a: 0, b: 0}
    for i in range(len(ps[a])):
        for t in (a, b):
            o = b if t == a else a
            if ps[t][i] > ps[o][i]:
                won[t] += 1
            if ps[t][i] >= 3:
                big[t] += 1
    rows = {x["label"]: x["values"] for x in g["sections"][0]["rows"]}
    for t in (a, b):
        scored_h = sum(1 for e in hb[t] if ps[t][e - 1] > 0)
        want = {
            "Ends won": str(won[t]),
            "Stolen ends": str(len(r["stolen"][t])),
            "Ends with hammer": str(len(hb[t])),
            "Scored with hammer": "%d of %d" % (scored_h, len(hb[t])),
            "Big ends (3+)": str(big[t]),
        }
        for label, val in want.items():
            if val is not None and rows[label][t] != val:
                _fail("curling game: %s for %s is %s, computed %s" % (label, t, rows[label][t], val))
    blank_owner = {a: 0, b: 0}
    for e in r["blank_ends"]:
        owner = a if e in hb[a] else b
        blank_owner[owner] += 1
    for t in (a, b):
        if rows["Blank ends"][t] != str(blank_owner[t]):
            _fail("curling game: blank ends for %s" % t)
    if won[a] + won[b] + len(r["blank_ends"]) != len(ps[a]):
        _fail("curling game: ends do not add up")
    for tm in g["final"]["teams"]:
        if tm["record_text"] != "%s · now %s" % (tm["result"], tm["record"]):
            _fail("curling game: record text")
        if tm["record"] != team("curling", tm["team"])["record"]:
            _fail("curling game: record != team record")


def _check_basketball_game(league):
    g = league["game"]
    r = [x for x in league["results"] if x["id"] == g["result"]][0]
    for row in g["line_score"]["rows"]:
        if row["cells"] != r["period_scores"][row["team"]] or sum(row["cells"]) != row["total"]:
            _fail("basketball game: line score")
        best = row["cells"].index(max(row["cells"])) + 1
        if g["line_score"]["highlight"]["periods"][row["team"]] != best:
            _fail("basketball game: biggest quarter for %s" % row["team"])
    total_pts = 0
    for box in g["box_scores"]:
        rows = box["rows"]
        t = box["totals"]
        for key in ("pts", "ftm", "fta", "pf"):
            if sum(x[key] for x in rows) != t[key]:
                _fail("basketball game: %s total for %s" % (key, box["team"]))
        if t["pts"] != box["score"] or box["score"] != r["scores"][box["team"]]:
            _fail("basketball game: box score total for %s" % box["team"])
        if t["label"] != "Team · %d played" % len(rows):
            _fail("basketball game: played count for %s" % box["team"])
        if box["note"] != "Free throws %.1f%%" % (100.0 * t["ftm"] / t["fta"]):
            _fail("basketball game: FT%% for %s" % box["team"])
        for x in rows:
            if x["ftm"] > x["fta"]:
                _fail("basketball game: FTM > FTA")
        total_pts += t["pts"]
    ts = g["top_scorer"]
    best = max((x for b in g["box_scores"] for x in b["rows"]), key=lambda x: x["pts"])
    if best["player"] != ts["player"] or best["pts"] != ts["value"]:
        _fail("basketball game: top scorer")
    w, l = sorted(r["scores"].values(), reverse=True)
    if g["final"]["sub"] != "%s by %d" % (team_name("basketball", r["winner"]), w - l):
        _fail("basketball game: margin text")


def _check_hockey_game(league):
    g = league["game"]
    r = [x for x in league["results"] if x["id"] == g["result"]][0]
    a, b = r["home"], r["away"]  # first-listed = the one written first in the running score
    secs = {s["kind"]: s for s in g["sections"]}
    # line score
    for row in g["line_score"]["rows"]:
        if row["cells"] != r["period_scores"][row["team"]] or sum(row["cells"]) != row["total"]:
            _fail("hockey game: line score")
    # scoring summary
    run = [0, 0]
    goals = {a: {}, b: {}}
    assists = {a: {}, b: {}}
    gwg = []
    for per in secs["scoring"]["periods"]:
        tally = {a: 0, b: 0}
        for gl in per["goals"]:
            idx = 0 if gl["team"] == a else 1
            run[idx] += 1
            tally[gl["team"]] += 1
            if gl["score"] != run:
                _fail("hockey game: running score at %s is %s, expected %s" % (gl["time"], gl["score"], run))
            lab = gl["scorer"]["label"]
            goals[gl["team"]][lab] = goals[gl["team"]].get(lab, 0) + 1
            for p in gl["assists"]:
                assists[gl["team"]][p["label"]] = assists[gl["team"]].get(p["label"], 0) + 1
            if gl["gwg"]:
                gwg.append(gl)
        if per["tally"] != tally:
            _fail("hockey game: period tally %s != %s" % (per["tally"], tally))
    if run != [r["scores"][a], r["scores"][b]]:
        _fail("hockey game: scoring summary does not end at the final score")
    for t in (a, b):
        per_period = [sum(1 for gl in per["goals"] if gl["team"] == t) for per in secs["scoring"]["periods"]]
        if per_period != r["period_scores"][t]:
            _fail("hockey game: goals per period for %s" % t)
    # game winning goal = the goal that made the winner's score one more than the loser's final
    loser_final = min(r["scores"].values())
    run = [0, 0]
    want_gwg = None
    for per in secs["scoring"]["periods"]:
        for gl in per["goals"]:
            run[0 if gl["team"] == a else 1] += 1
            win_i = 0 if r["winner"] == a else 1
            if want_gwg is None and run[win_i] == loser_final + 1 and gl["team"] == r["winner"]:
                want_gwg = gl
    if len(gwg) != 1 or gwg[0] is not want_gwg or r["gwg"] != gwg[0]["scorer"]:
        _fail("hockey game: game-winning goal flag")
    # penalties
    pim = {a: {}, b: {}}
    for pen in secs["penalties"]["rows"]:
        lab = pen["player"]["label"]
        pim[pen["team"]][lab] = pim[pen["team"]].get(lab, 0) + pen["minutes"]
    # goalies
    for gr in secs["goalies"]["rows"]:
        opp = b if gr["team"] == a else a
        if gr["ga"] != r["scores"][opp]:
            _fail("hockey game: goalie GA for %s" % gr["team"])
        if gr["result"] != ("W" if r["winner"] == gr["team"] else "L"):
            _fail("hockey game: goalie result")
    if [p["label"] for p in g["line_score"]["foot_goalies"]] != [x["player"]["label"] for x in secs["goalies"]["rows"]]:
        _fail("hockey game: goalies line")
    # skaters
    for tb in secs["skaters"]["teams"]:
        t = tb["team"]
        tot = {"g": 0, "a": 0, "pts": 0, "pim": 0}
        labels = set()
        for row in tb["rows"]:
            lab = row["player"]["label"]
            labels.add(lab)
            if row["g"] != goals[t].get(lab, 0) or row["a"] != assists[t].get(lab, 0):
                _fail("hockey game: %s G/A does not match the scoring summary" % lab)
            if row["pim"] != pim[t].get(lab, 0):
                _fail("hockey game: %s PIM does not match penalties" % lab)
            if row["g"] + row["a"] != row["pts"]:
                _fail("hockey game: %s G+A != PTS" % lab)
            if (row["g"], row["a"], row["pim"]) == (0, 0, 0):
                _fail("hockey game: %s has nothing to list" % lab)
            for k in tot:
                tot[k] += row[k]
        if tot != tb["total"]:
            _fail("hockey game: totals for %s: %s != %s" % (t, tb["total"], tot))
        if tot["g"] != r["scores"][t]:
            _fail("hockey game: skater goals for %s != team score" % t)
        for lab in list(goals[t]) + list(assists[t]) + list(pim[t]):
            if lab not in labels:
                _fail("hockey game: %s missing from skaters table" % lab)
        if g["line_score"]["foot_pim"][t] != tot["pim"]:
            _fail("hockey game: PIM line for %s" % t)
    for tm in g["final"]["teams"]:
        if tm["record_text"] != "%s · %s" % (tm["record"], tm["result"]):
            _fail("hockey game: record text")
        if tm["record"] != team("hockey", tm["team"])["record"]:
            _fail("hockey game: record != team record")


def _check_slopitch_game(league):
    g = league["game"]
    r = [x for x in league["results"] if x["id"] == g["result"]][0]
    ls = g["line_score"]
    for row in ls["rows"]:
        t = row["team"]
        if row["cells"] != r["period_scores"][t] or row["total"] != r["scores"][t] or row["hits"] != r["hits"][t]:
            _fail("slopitch game: line score differs from the result")
    if ls["limit_innings"] != r["limit_innings"] or ls["x_innings"] != r["x_innings"]:
        _fail("slopitch game: limit/X innings differ from the result")
    ordinals = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th"}
    batting = {}
    for s in g["sections"]:
        if s["kind"] != "batting":
            continue
        t = s["team"]
        batting[t] = s
        rows = s["rows"]
        if [x["order"] for x in rows] != list(range(1, len(rows) + 1)):
            _fail("slopitch game: batting order for %s" % t)
        for key in ("ab", "r", "h", "rbi", "hr"):
            if sum(x[key] for x in rows) != s["totals"][key]:
                _fail("slopitch game: %s total for %s is %d, Totals row says %d" % (
                    key, t, sum(x[key] for x in rows), s["totals"][key]))
        if s["totals"]["r"] != r["scores"][t] or s["totals"]["h"] != r["hits"][t]:
            _fail("slopitch game: totals row differs from line score for %s" % t)
        for x in rows:
            if x["h"] > x["ab"] or x["hr"] > x["h"]:
                _fail("slopitch game: impossible batting line %s" % x["player"]["label"])
    facts = {}
    for s in g["sections"]:
        if s["kind"] == "facts":
            for row in s["rows"]:
                facts[row["label"]] = row
    for label, key, test in (("Home runs", "hr", lambda v: v >= 1), ("3 hits", "h", lambda v: v == 3)):
        for grp in facts[label]["groups"]:
            want = [x["player"]["label"] for x in batting[grp["team"]]["rows"] if test(x[key])]
            if [p["label"] for p in grp["players"]] != want:
                _fail("slopitch game: '%s' fact for %s should be %s" % (label, grp["team"], want))
        for t in batting:
            have = any(grp["team"] == t for grp in facts[label]["groups"])
            has_any = any(test(x[key]) for x in batting[t]["rows"])
            if have != has_any:
                _fail("slopitch game: '%s' fact misses a team" % label)
    for lim in facts["Limit innings"]["limit"]:
        inns = r["limit_innings"][lim["team"]]
        if lim["count"] != len(inns) or lim["innings"] != [ordinals[i] for i in inns]:
            _fail("slopitch game: limit innings fact for %s" % lim["team"])
    # visitors / home
    roles = {tm["team"]: tm["role"] for tm in g["final"]["teams"]}
    if roles[r["designated_home"]] != "Home":
        _fail("slopitch game: home team role")
    for tm in g["final"]["teams"]:
        if tm["record_text"] != "%s · %s" % (tm["role"], tm["record"]):
            _fail("slopitch game: record text")
        if tm["record"] != team("slopitch", tm["team"])["record"]:
            _fail("slopitch game: record != team record")


def check():
    # layouts
    ids = [l["id"] for l in LAYOUTS]
    if ids != ["basketball", "curling", "hockey", "slopitch", "classic", "scoreboard"]:
        _fail("LAYOUTS order/ids: %s" % ids)
    for l in LAYOUTS:
        if l["kind"] not in ("sport", "general"):
            _fail("layout kind")
        if len(l["fonts"]) != 2:
            _fail("layout fonts")
        for s in l["sports"]:
            if s not in LEAGUES:
                _fail("layout %s shows unknown sport %s" % (l["id"], s))
    for l in LAYOUTS:
        if l["kind"] == "sport" and l["sports"] != [l["id"]]:
            _fail("sport layout %s must show its own sport" % l["id"])
    # alt colours
    for c in ALT_LEAGUE_COLOURS:
        if not _HEX_RE.match(c["hex"]):
            _fail("alt colour %r" % c)
    if sum(1 for c in ALT_LEAGUE_COLOURS if c.get("expected_fail")) != 1:
        _fail("ALT_LEAGUE_COLOURS should have exactly one expected_fail colour (Gold)")
    # leagues
    people = 0
    for sport, lg in LEAGUES.items():
        if lg["sport"] != sport:
            _fail("league sport key")
        _check_league(sport, lg)
        people += _check_people(sport, lg)
        for t in lg["teams"]:
            for k in ("light", "dark"):
                if not _HEX_RE.match(t["mockup_hex"][k]):
                    _fail("bad mockup hex for %s" % t["id"])
        if lg["game"]["result"] not in {r["id"] for r in lg["results"]}:
            _fail("%s: game's result missing" % sport)
        for sec in ("results_header", "next_day", "leaders", "standings"):
            if sec not in lg:
                _fail("%s: missing %s" % (sport, sec))
    _check_basketball_game(BASKETBALL)
    _check_curling_game(CURLING)
    _check_hockey_game(HOCKEY)
    _check_slopitch_game(SLOPITCH)
    return people


def _summary(people):
    print("scripts.design_system.sample: OK")
    print("  layouts: %s" % ", ".join("%s (%s)" % (l["id"], "+".join(l["sports"])) for l in LAYOUTS))
    print("  alt league colours: %s" % ", ".join("%s %s" % (c["name"], c["hex"]) for c in ALT_LEAGUE_COLOURS))
    for sport, lg in LEAGUES.items():
        withp = sum(1 for r in lg["results"] if r["period_scores"] is not None)
        lead_rows = sum(len(x["rows"]) for x in lg["leaders"]["lists"])
        print("  %-10s %s: %d teams, %d standings cols, %d results (%d with by-period scores), "
              "%d next-day games, %d leader tiles, %d leader rows, game %s" % (
                  sport, lg["code"], len(lg["teams"]), len(lg["standings"]["columns"]), len(lg["results"]),
                  withp, sum(len(g["rows"]) for g in lg["next_day"]["groups"]), len(lg["leaders"]["tiles"]),
                  lead_rows, lg["game"]["id"]))
    print("  people checked ('First L.'): %d" % people)


if __name__ == "__main__":
    _summary(check())
