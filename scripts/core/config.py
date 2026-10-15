"""league.yml: loading, checking, defaults, placeholders and the league-colour gate (spec 2.1, 4.4, 4.6).

`load_league()` returns `(League | None, problems)`: the League is None when any problem is an error. Every
problem names `league.yml` and a path inside it. The settings a sport marks `decide: true` and the league has
not set become `League.placeholders` ("Unset means placeholder"). `effective_settings()` applies a season's
`overrides` from seasons.yml on top.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scripts.core.fmt import humanize
from scripts.core.problems import Checker, display_path, join_path, read_yaml
from scripts.core.sports import (
    ID_RE, REPO_ROOT, SPORTS_ROOT, check_option_value, check_standings, discover_sports, is_wrapped, load_sport,
    team_stat_keys, unknown_sport_message, unwrap,
)
from scripts.core.types import LAYOUTS, League, Placeholder, Problem, SportDef

LEAGUE_FILE = "league.yml"
LEAGUE_KEYS = ("name", "short_name", "code", "sport", "layout", "colour", "colour_dark", "logo", "tagline",
               "footer_line", "contact", "timezone", "time_format", "lang", "search_engines", "sample_data",
               "preview", "photos", "rules", "standings", "stats", "labels", "calendar", "github")
REQUIRED_KEYS = ("name", "sport", "timezone")
TIME_FORMATS = ("12h", "24h")
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")
CODE_RE = re.compile(r"[A-Za-z]{1,4}")
LANG_RE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
URL_RE = re.compile(r"https?://\S+")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LOGO_SUFFIXES = (".svg", ".png")

# Used only when neither the sport nor league.yml says (the sport's standings should always say).
FALLBACK_STANDINGS: dict[str, Any] = {
    "rank_by": "points", "points": {"win": 2, "tie": 1, "loss": 0}, "period_points": 0, "ties": True,
    "forfeit": {"score": [1, 0]}, "tiebreakers": [], "columns": ["gp", "w", "l", "t", "pts", "pf", "pa", "diff"],
    "playoffs": None,
}


# ------------------------------------------------------------------ merging

def deep_merge(base: dict, over: dict) -> dict:
    """`over` laid on `base`: maps merge key by key, everything else (lists, numbers, text) is replaced.
    Neither argument is changed."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def normalise_standings(merged: dict) -> dict:
    """Fill what is still missing: ot_win defaults to win, ot_loss to loss; the other keys take the core's
    fallbacks. The result always has rank_by, points (all five), period_points, ties, forfeit, tiebreakers,
    columns and playoffs."""
    out = deep_merge(FALLBACK_STANDINGS, merged)
    points = out["points"]
    points.setdefault("ot_win", points["win"])
    points.setdefault("ot_loss", points["loss"])
    return out


def sport_standings_defaults(spec: dict) -> dict:
    """The sport's standings with every `{value, decide}` wrapper removed."""
    return {key: unwrap(value)[0] for key, value in spec["standings"].items()}


def sport_decide_settings(spec: dict) -> list[tuple[str, str]]:
    """[(setting path in league.yml, words for it)] for everything the sport marks `decide: true`, in
    sport.yml order: rules options, then standings keys, then minimums."""
    found = []
    for key, opt in spec["options"].items():
        if opt.get("decide"):
            found.append((join_path("rules", key), opt.get("label") or humanize(key)))
    for key, value in spec["standings"].items():
        if is_wrapped(value) and value.get("decide"):
            found.append((join_path("standings", key), humanize(key)))
    for key, m in spec["minimums"].items():
        if m.get("decide"):
            found.append((join_path("stats", "minimums", key), m.get("label") or humanize(key)))
    return found


def _is_set(raw: dict, path: str) -> bool:
    node: Any = raw
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def find_placeholders(spec: dict, raw: dict) -> tuple[Placeholder, ...]:
    """Every `decide: true` setting that league.yml (the parsed `raw` mapping) leaves out. Setting a value,
    even the same as the default, removes the placeholder."""
    return tuple(Placeholder(path, text) for path, text in sport_decide_settings(spec) if not _is_set(raw, path))


# ------------------------------------------------------------------ the sections that depend on the sport

def check_rules(c: Checker, raw: Any, at: str, spec: dict) -> None:
    """league.yml `rules:` (or a season's): keys must be sport options, values must fit their type."""
    options = spec["options"]
    if c.mapping(raw, at, allowed=options) is None:
        return
    for key, value in raw.items():
        if key in options:
            check_option_value(c, value, join_path(at, key), options[key])


def check_minimums(c: Checker, raw: Any, at: str, spec: dict) -> None:
    """`stats.minimums`: keys must be the sport's minimums, values whole numbers."""
    if c.mapping(raw, at, allowed=spec["minimums"]) is None:
        return
    for key, value in raw.items():
        if key in spec["minimums"]:
            c.integer(value, join_path(at, key), 0, 999)


def check_stats(c: Checker, raw: Any, at: str, spec: dict) -> None:
    if c.mapping(raw, at, allowed=("minimums",)) is not None and "minimums" in raw:
        check_minimums(c, raw["minimums"], join_path(at, "minimums"), spec)


def check_labels(c: Checker, raw: Any, at: str, spec: dict) -> None:
    known = {*spec["labels"], *(k for labels in spec["labels_by_layout"].values() for k in labels)}
    if c.mapping(raw, at, allowed=sorted(known)) is not None:
        for key, value in raw.items():
            c.text(value, join_path(at, key))


# ------------------------------------------------------------------ the other keys

def default_code(name: str) -> str:
    """The monogram when `code` is not set: the initials of the words of the name, up to 4 letters."""
    initials = [w[0] for w in re.split(r"[\s\-]+", name) if w and w[0].isalpha()]
    return "".join(initials[:4]).upper() or "L"


def _check_timezone(c: Checker, value: Any) -> None:
    if c.text(value, "timezone") is None:
        return
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        c.error("timezone", f"{value!r} is not a time zone name. Use a name such as 'America/Toronto' or "
                            "'Europe/London' (the 'TZ identifier' column of the Wikipedia list of tz database time zones).")


def _check_contact(c: Checker, value: Any) -> str | None:
    """Returns the href for the footer link ('mailto:' added to an email), or None."""
    if c.text(value, "contact") is None:
        return None
    value = value.strip()
    if EMAIL_RE.fullmatch(value):
        return "mailto:" + value
    if URL_RE.fullmatch(value):
        return value
    c.error("contact", f"{value!r} is neither an email address nor a web address starting with http:// or https://.")
    return None


def _check_logo(c: Checker, value: Any, root: Path) -> None:
    if c.text(value, "logo") is None:
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("/"):
        c.error("logo", f"{value!r} must be a path inside the repository, like assets/league/logo.svg (no leading '/').")
    elif path.suffix.lower() not in LOGO_SUFFIXES:
        c.error("logo", f"{value!r} must be an .svg or .png file (square, at least 96 px).")
    elif not (root / path).is_file():
        c.error("logo", f"{value!r} does not exist. Put the file there, or delete the 'logo:' line to use the monogram badge.")


def _check_github(c: Checker, value: Any) -> dict | None:
    if c.mapping(value, "github", allowed=("branch",), required=("repo",)) is None:
        return None
    if "repo" in value:
        c.pattern(value["repo"], "github.repo", REPO_RE, "'owner/name', like 'my-league/website'")
    if "branch" in value:
        c.text(value["branch"], "github.branch")
    return {"repo": value.get("repo"), "branch": value.get("branch", "main")}


def _check_colours(c: Checker, raw: dict, layout: str | None) -> tuple[str | None, str | None]:
    """The two hex colours (upper case), and the contrast gate (spec 4.6) when `colour` is fine."""
    out: dict[str, str | None] = {"colour": None, "colour_dark": None}
    for key in ("colour", "colour_dark"):
        if key in raw and c.pattern(raw[key], key, HEX_RE, "a colour like '#1D3A6E' (a # and six hex digits)"):
            out[key] = raw[key].upper()
    if "colour_dark" in raw and "colour" not in raw:
        c.error("colour_dark", "needs 'colour' as well: colour_dark is the dark-theme version of the league colour.")
    if out["colour"] and layout in LAYOUTS:
        from scripts.check_contrast import check_league_colour    # loaded only when a colour is set
        for p in check_league_colour(layout, out["colour"], out["colour_dark"]):
            c.error(p.setting or "colour", p.message)
    return out["colour"], out["colour_dark"]


# ------------------------------------------------------------------ the whole file

def build_league(raw: Any, *, file: str = LEAGUE_FILE, sports_root: Path = SPORTS_ROOT,
                 root: Path = REPO_ROOT) -> tuple[League | None, list[Problem]]:
    """Check a parsed league.yml (`raw`) and apply the defaults. Returns (League, problems); the League is
    None when any problem is an error. Everything is checked even after the first problem."""
    c = Checker(file)
    if raw is None:
        c.error("", "This file is empty. It needs at least: " + ", ".join(REQUIRED_KEYS) + ".")
        return None, c.problems
    if c.mapping(raw, "", allowed=LEAGUE_KEYS, required=REQUIRED_KEYS) is None:
        return None, c.problems

    name = c.text(raw["name"], "name") if "name" in raw else None
    sport = _load_sport(c, raw, sports_root, root)
    spec = sport.spec if sport else None
    short_name = c.text(raw["short_name"], "short_name") if "short_name" in raw else name
    code = c.pattern(raw["code"], "code", CODE_RE, "1 to 4 letters, like 'EVSL'") if "code" in raw else None
    layout = c.choice(raw["layout"], "layout", LAYOUTS) if "layout" in raw else (spec["default_layout"] if spec else None)
    colour, colour_dark = _check_colours(c, raw, layout)
    if "logo" in raw:
        _check_logo(c, raw["logo"], root)
    tagline = c.text(raw["tagline"], "tagline") if "tagline" in raw else (spec["name"] if spec else "")
    footer_line = c.text(raw["footer_line"], "footer_line") if "footer_line" in raw else None
    contact_href = _check_contact(c, raw["contact"]) if "contact" in raw else None
    if "timezone" in raw:
        _check_timezone(c, raw["timezone"])
    time_format = c.choice(raw["time_format"], "time_format", TIME_FORMATS) if "time_format" in raw else "12h"
    lang = c.pattern(raw["lang"], "lang", LANG_RE, "a language code like 'en' or 'fr-CA'") if "lang" in raw else "en"
    flags = {k: (c.boolean(raw[k], k) if k in raw else default)
             for k, default in (("search_engines", False), ("sample_data", False), ("preview", True), ("photos", False))}
    github = _check_github(c, raw["github"]) if "github" in raw else None
    game_minutes = _check_calendar(c, raw, spec)

    rules, standings_merged, minimums, labels = {}, {}, {}, {}
    if spec:
        rules, standings_merged, minimums, labels = _sport_sections(c, raw, spec, layout)
    if not c.ok or name is None or spec is None:
        return None, c.problems
    league = League(
        name=name, short_name=short_name or name, code=(code or default_code(name)).upper(), sport=sport.id,
        layout=layout, colour=colour, colour_dark=colour_dark, logo=raw.get("logo"), tagline=tagline,
        footer_line=footer_line, contact=raw.get("contact"), contact_href=contact_href, timezone=raw["timezone"],
        time_format=time_format, lang=lang, search_engines=flags["search_engines"], sample_data=flags["sample_data"],
        preview=flags["preview"], photos=flags["photos"], rules=rules, standings=normalise_standings(standings_merged),
        standings_merged=standings_merged, minimums=minimums, labels=labels, game_minutes=game_minutes, github=github,
        placeholders=find_placeholders(spec, raw), sport_def=sport)
    return league, c.problems


def _load_sport(c: Checker, raw: dict, sports_root: Path, root: Path) -> SportDef | None:
    """Find and load the league's sport. Problems in the sport's own files keep their own file names."""
    sport_id = raw.get("sport")
    if "sport" not in raw:
        return None
    if not isinstance(sport_id, str) or not ID_RE.fullmatch(sport_id) or sport_id not in discover_sports(sports_root):
        c.error("sport", unknown_sport_message(sport_id, sports_root, root))
        return None
    sport, problems = load_sport(sport_id, sports_root, root=root)
    c.problems.extend(problems)
    return sport


def _check_calendar(c: Checker, raw: dict, spec: dict | None) -> int:
    default = spec["game_minutes"] if spec else 60
    if "calendar" in raw and c.mapping(raw["calendar"], "calendar", allowed=("game_minutes",)) is not None \
            and "game_minutes" in raw["calendar"]:
        return c.integer(raw["calendar"]["game_minutes"], "calendar.game_minutes", 1, 1440) or default
    return default


def _sport_sections(c: Checker, raw: dict, spec: dict, layout: str | None) -> tuple[dict, dict, dict, dict]:
    """rules, standings (merged over the sport's), minimums and labels, checked against the sport."""
    if "rules" in raw:
        check_rules(c, raw["rules"], "rules", spec)
    if "standings" in raw:
        check_standings(c, raw["standings"], "standings", team_stat_keys(spec))
    if "stats" in raw:
        check_stats(c, raw["stats"], "stats", spec)
    if "labels" in raw:
        check_labels(c, raw["labels"], "labels", spec)
    if not c.ok:
        return {}, {}, {}, {}
    return _merged_sections(raw, spec, layout)


def _merged_sections(raw: dict, spec: dict, layout: str | None) -> tuple[dict, dict, dict, dict]:
    rules = {key: opt["default"] for key, opt in spec["options"].items()} | (raw.get("rules") or {})
    standings = deep_merge(sport_standings_defaults(spec), raw.get("standings") or {})
    minimums = {key: m["default"] for key, m in spec["minimums"].items()} | ((raw.get("stats") or {}).get("minimums") or {})
    labels = {**spec["labels"], **spec["labels_by_layout"].get(layout, {}), **(raw.get("labels") or {})}
    return rules, standings, minimums, labels


def load_league(path: Path | None = None, *, sports_root: Path = SPORTS_ROOT,
                root: Path = REPO_ROOT) -> tuple[League | None, list[Problem]]:
    """Read, check and complete league.yml (default: `league.yml` in the repo root). Returns
    (League, problems): the League is None when any problem is an error."""
    path = path or root / LEAGUE_FILE
    file = display_path(path, root)
    raw, problems = read_yaml(path, file)
    if problems:
        return None, problems
    return build_league(raw, file=file, sports_root=sports_root, root=root)


# ------------------------------------------------------------------ per-season overrides

@dataclass(frozen=True)
class Settings:
    """The rules, standings and minimums that hold for one season."""
    rules: dict
    standings: dict
    minimums: dict[str, int]


def effective_settings(league: League, overrides: Any = None, *, file: str = "data/seasons.yml",
                       at: str = "overrides") -> tuple[Settings, list[Problem]]:
    """The league's settings with a season's `overrides:` (from seasons.yml) deep-merged over them, so a
    changed points rule does not rewrite an archived season. Overrides take `rules`, `standings` and
    `stats.minimums`, and are checked like league.yml; problems carry `file` and a path starting with `at`
    (the caller passes e.g. "1.overrides" for the second season). With no overrides, the league's own."""
    base = Settings(league.rules, league.standings, league.minimums)
    if overrides is None:
        return base, []
    c, spec = Checker(file), league.sport_def.spec
    if c.mapping(overrides, at, allowed=("rules", "standings", "stats")) is None:
        return base, c.problems
    if "rules" in overrides:
        check_rules(c, overrides["rules"], join_path(at, "rules"), spec)
    if "standings" in overrides:
        check_standings(c, overrides["standings"], join_path(at, "standings"), team_stat_keys(spec))
    if "stats" in overrides:
        check_stats(c, overrides["stats"], join_path(at, "stats"), spec)
    if not c.ok:
        return base, c.problems
    rules = deep_merge(league.rules, overrides.get("rules") or {})
    standings = normalise_standings(deep_merge(league.standings_merged, overrides.get("standings") or {}))
    minimums = deep_merge(league.minimums, (overrides.get("stats") or {}).get("minimums") or {})
    return Settings(rules, standings, minimums), c.problems
