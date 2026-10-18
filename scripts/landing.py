#!/usr/bin/env python3
"""The landing page's data (docs/landing-page-plan.md, sections 1 to 3 and 5).

With `landing_page: true` in league.yml the front page of the site is a showcase: one card per sport demo with a
small live preview (the top of its standings and its latest result). This module checks `landing.yml` (the page's
own words) and the sports' `blurb:` lines, builds every demo league the way `/<sport>/` is built, and keeps a
small extract of each: `_data/computed/landing.json`. It also writes `_config.landing.yml`, the Jekyll overlay that
leaves the league's own pages out of the root build.

    python scripts/landing.py [--out FILE]      # print (or write) landing.json for the league.yml in this repository

`scripts/build.py` calls `read_words()` on every run (so `--check` reports landing.yml problems) and `build_page()`
and `write_overlay()` on a plain run. Nothing here is read when the switch is off, except that the overlay then
says `landing_page: false`.

landing.json (every `url` is a site path, for `relative_url`):

    shell     what shell/header, nav, footer and 404 read as `league`: name, short_name, code, layout, tagline, lang,
              search_engines, footer_name, footer_line, nav [{label, url, key}], footer_links [{label, url}], labels,
              extra_layouts (the layouts the cards' windows need besides the page's own)
    active    {sample_mode: false, preview: false}: what shell/sample-banner reads as `active`
    intro     {eyebrow, title, text}
    links     [{label, url, note}]       features_title, features [text]       copy_note
    sports    [{id, name, blurb, url, demo_label, league_name, layout, window}]  one per demo sport shown
      window  {league {name, layout, labels, words, display, results_legend},
               standings {columns, rows, note}, teams {id: {name, code, slot, colour, url}},
               latest {label, date_long, game} | null}
    coming_soon  [{id, name, blurb}]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.compute import compute                                             # noqa: E402
from scripts.core.config import LEAGUE_FILE, load_league                             # noqa: E402
from scripts.core.loader import load_data                                            # noqa: E402
from scripts.core.model import League, Problem                                       # noqa: E402
from scripts.core.problems import (                                                  # noqa: E402
    Checker, has_errors, join_path, read_yaml, with_file,
)
from scripts.core.sports import BLURB_MAX, demo_sports                                          # noqa: E402

LANDING_FILE = "landing.yml"
OVERLAY_FILE = "_config.landing.yml"
LANDING_LAYOUT = "basketball"          # the landing page uses the Basketball look
WINDOW_ROWS = 3                        # standings rows on a card
LANDING_KEYS = ("name", "code", "tagline", "eyebrow", "title", "intro", "nav", "demo_label", "links", "features_title",
                "features", "copy_note", "coming_soon")
LANDING_REQUIRED = ("name", "code", "tagline", "eyebrow", "title", "intro", "nav", "links", "features", "coming_soon")
SHELL_LABELS = {"standings": "Standings", "leaders": "Leaders", "final": "Final"}
DEFAULT_DEMO_LABEL = "Open the {name} demo"
# The league's own pages at the site root: left out of the root build while the landing page is on. A page added
# to the root later (the entry page, say) must be added here (tests/test_landing.py lists the root and fails on any
# page it does not know).
LEAGUE_PAGES = ("index.html", "schedule/", "stats/", "teams/", "archive/", "rules/", "calendar/")
COLLECTIONS = ("games", "players", "teams", "archive")
# Keys of a game the result card never reads (the box score and the notes): left out of the extract.
GAME_LEFT_OUT = ("blocks", "tiles", "notes", "checked_by", "scorekeeper", "photo_url")
NOTE = ("The front page is the scorers-table landing page. For your league's own site, set landing_page: false "
        "in league.yml.")
# Not `jekyll serve` with the demos: serve rebuilds _site/ whenever build_preview.sh swaps the data, which deletes them.
SERVE_HINT = ("To see it with the demos it links to: bundle exec jekyll build --config _config.yml,_config.landing.yml, "
              "then scripts/build_preview.sh, then python -m http.server 4000 --directory _site (not jekyll serve: it "
              "rebuilds _site/ and deletes the demos).")
URL_WORDS = "must start with https:// or be a path of this site, like /basketball/."


# ------------------------------------------------------------------ landing.yml and the blurbs

def _url(c: Checker, value: Any, at: str) -> str | None:
    text = c.text(value, at)
    if text is not None and not (text.startswith("https://") or (text.startswith("/") and not text.startswith("//"))):
        c.error(at, f"{text!r} {URL_WORDS}")
        return None
    return text


def _short(c: Checker, value: Any, at: str) -> str | None:
    text = c.text(value, at)
    if text is not None and len(text) > BLURB_MAX:
        c.error(at, f"is {len(text)} characters; keep it to at most {BLURB_MAX}.")
        return None
    return text


def read_blurbs(ids: list[str], sports_root: Path) -> tuple[dict[str, str], list[Problem]]:
    """({sport id: blurb}, problems) for the sports on the page. A sport without a blurb (one line, at most 100
    characters) is an error in its own sport.yml."""
    found: dict[str, str] = {}
    problems: list[Problem] = []
    for sport_id in ids:
        file = f"sports/{sport_id}/sport.yml"
        spec, found_problems = read_yaml(sports_root / sport_id / "sport.yml", file)
        problems += found_problems
        if found_problems or not isinstance(spec, dict):
            continue
        blurb = spec.get("blurb")
        if isinstance(blurb, str) and blurb.strip() and len(blurb) <= BLURB_MAX and "\n" not in blurb.strip():
            found[sport_id] = blurb.strip()
        else:
            problems.append(Problem("error", "blurb", "a sport on the landing page needs a one-line blurb "
                                    f"(at most {BLURB_MAX} characters).", file))
    return found, problems


def read_words(league: League, root: Path = ROOT, *, sports_root: Path | None = None
               ) -> tuple[dict | None, list[Problem]]:
    """Read and check landing.yml for a league with `landing_page: true`, and the blurbs of the sports it shows.
    Returns (the checked words, problems); the words are None when there is an error."""
    sports_root = sports_root or root / "sports"
    path = root / LANDING_FILE
    if not path.is_file():
        return None, [Problem("error", "", "landing_page: true in league.yml needs this file (the words of the front "
                              "page). Put it back from the template, or set landing_page: false.", LANDING_FILE)]
    raw, problems = read_yaml(path, LANDING_FILE)
    if problems:
        return None, problems
    c = Checker(LANDING_FILE)
    if raw is None:
        c.error("", "This file is empty. It needs at least: " + ", ".join(LANDING_REQUIRED) + ".")
        return None, c.problems
    if c.mapping(raw, "", allowed=LANDING_KEYS, required=LANDING_REQUIRED) is None:
        return None, c.problems
    words: dict[str, Any] = {}
    for key in ("name", "tagline", "eyebrow", "title"):
        if key in raw:
            words[key] = c.text(raw[key], key)
    if "code" in raw:
        words["code"] = c.pattern(raw["code"], "code", re.compile(r"[A-Za-z]{1,4}"), "1 to 4 letters, like 'ST'")
    if "intro" in raw:
        text = c.text(raw["intro"], "intro")
        words["intro"] = " ".join(text.split()) if text else text
    if "copy_note" in raw:
        words["copy_note"] = c.text(raw["copy_note"], "copy_note")
    if "features_title" in raw:
        words["features_title"] = c.text(raw["features_title"], "features_title")
    if "demo_label" in raw:
        label = c.text(raw["demo_label"], "demo_label")
        if label is not None and "{name}" not in label:
            c.error("demo_label", "must contain {name}, where the sport's name goes, like 'Open the {name} demo'.")
            label = None
        words["demo_label"] = label
    words["nav"] = _check_nav(c, raw["nav"]) if "nav" in raw else None
    words["links"] = _check_links(c, raw["links"]) if "links" in raw else None
    words["features"] = _check_features(c, raw["features"]) if "features" in raw else None
    shown = list(league.sport_previews)
    words["coming_soon"] = _check_coming_soon(c, raw["coming_soon"], sports_root) if "coming_soon" in raw else None
    _, found = read_blurbs(shown, sports_root)
    problems = c.problems + found
    if has_errors(problems):
        return None, problems
    words.setdefault("demo_label", DEFAULT_DEMO_LABEL)
    words.setdefault("features_title", "")
    words.setdefault("copy_note", "")
    return words, problems


def _check_nav(c: Checker, value: Any) -> list[dict] | None:
    items = c.sequence(value, "nav")
    out = []
    for i, item in enumerate(items or []):
        at = join_path("nav", i)
        if c.mapping(item, at, allowed=("label", "url", "key"), required=("label", "url", "key")) is None:
            continue
        if not all(k in item for k in ("label", "url", "key")):
            continue                                             # the missing one is already an error
        label, url, key = (c.text(item["label"], join_path(at, "label")), _url(c, item["url"], join_path(at, "url")),
                           c.ident(item["key"], join_path(at, "key")))
        if None not in (label, url, key):
            out.append({"label": label, "url": url, "key": key})
    return out if items is not None else None


def _check_links(c: Checker, value: Any) -> list[dict] | None:
    items = c.sequence(value, "links")
    out = []
    for i, item in enumerate(items or []):
        at = join_path("links", i)
        if c.mapping(item, at, allowed=("label", "url", "note"), required=("label", "url")) is None:
            continue
        if not all(k in item for k in ("label", "url")):
            continue
        label, url = c.text(item["label"], join_path(at, "label")), _url(c, item["url"], join_path(at, "url"))
        note = c.text(item["note"], join_path(at, "note"), allow_empty=True) if "note" in item else ""
        if None not in (label, url, note):
            out.append({"label": label, "url": url, "note": note})
    return out if items is not None else None


def _check_features(c: Checker, value: Any) -> list[str] | None:
    items = c.sequence(value, "features")
    out = [c.text(item, join_path("features", i)) for i, item in enumerate(items or [])]
    return [t for t in out if t is not None] if items is not None else None


def _check_coming_soon(c: Checker, value: Any, sports_root: Path) -> list[dict] | None:
    """The planned sports. One that has a demo now is dropped (its card is a real one), with a warning."""
    items = c.sequence(value, "coming_soon")
    demos = demo_sports(sports_root)
    out: list[dict] = []
    for i, item in enumerate(items or []):
        at = join_path("coming_soon", i)
        if c.mapping(item, at, allowed=("id", "name", "blurb"), required=("id", "name", "blurb")) is None:
            continue
        if not all(k in item for k in ("id", "name", "blurb")):
            continue
        sport_id, name = c.ident(item["id"], join_path(at, "id")), c.text(item["name"], join_path(at, "name"))
        blurb = _short(c, item["blurb"], join_path(at, "blurb"))
        if sport_id is None or name is None or blurb is None:
            continue
        if any(o["id"] == sport_id for o in out):
            c.error(join_path(at, "id"), f"{sport_id!r} is listed twice.")
        elif sport_id in demos:
            c.warning(at, f"{sport_id!r} has a demo now, so it gets a real card. Take it off coming_soon.")
        else:
            out.append({"id": sport_id, "name": name, "blurb": blurb})
    return out if items is not None else None


# ------------------------------------------------------------------ one demo league

def _prefix_urls(value: Any, prefix: str) -> Any:
    """A copy with every `url` (a site path) moved into the demo: /games/x/ becomes /basketball/games/x/."""
    if isinstance(value, dict):
        return {k: (prefix + v if k == "url" and isinstance(v, str) and v.startswith("/") else _prefix_urls(v, prefix))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_prefix_urls(v, prefix) for v in value]
    return value


def _window(sport_id: str, output, blurb: str) -> dict:
    """The sport entry for one built demo (`output` is the demo's BuildOutput)."""
    data, sid, prefix = output.data, output.active, f"/{sport_id}"
    demo = data["league.json"]
    standings, teams = data[f"{sid}/standings.json"], data[f"{sid}/teams.json"]
    key = next((i for i, col in enumerate(standings["columns"]) if col["key_col"]), len(standings["columns"]) - 1)
    columns = standings["columns"][:key + 1]
    race = demo["layout"] == "scoreboard"                      # only the race reads these two
    rows = [{"rank": r["rank"], "team": r["team"], "display": {c["key"]: r["display"][c["key"]] for c in columns},
             **({"race": r["race"]} if race else {})} for r in standings["rows"][:WINDOW_ROWS]]
    total, through = len(standings["rows"]), standings.get("through_display") or ""
    count = f"Top {WINDOW_ROWS} of {total}" if total > WINDOW_ROWS else f"All {total} teams"
    window_standings = {"columns": columns, "rows": rows, "note": f"{count} · through {through}" if through else count}
    if race:
        window_standings["race"] = standings["race"]
    shown = {t: _prefix_urls({k: teams[t][k] for k in ("name", "code", "slot", "colour", "url")}, prefix)
             for t in dict.fromkeys(r["team"] for r in rows)}
    latest = None
    results = data[f"{sid}/results.json"]
    if results:
        day = next(d for d in data[f"{sid}/schedule.json"]["days"] if d["n"] == results[0]["day"])
        game = data[f"{sid}/games.json"][results[0]["games"][0]]
        latest = {"label": day["label"], "date_long": day["date_long"],
                  "game": _prefix_urls({k: v for k, v in game.items() if k not in GAME_LEFT_OUT}, prefix)}
    window_league = {k: demo[k] for k in ("name", "layout", "labels", "words", "display", "results_legend")}
    return {"name": demo["sport_name"], "blurb": blurb, "league_name": demo["name"], "layout": demo["layout"],
            "window": {"league": window_league, "standings": window_standings, "teams": shown, "latest": latest}}


def build_demo(sport_id: str, root: Path = ROOT, *, today=None):
    """Build one sport's demo league exactly as `/<sport_id>/` is built (scripts/build_preview.sh: the temporary
    root of scripts/preview_root.py, then build.py --sport-preview). Returns (BuildOutput, problems)."""
    from scripts import preview_root              # here, not at the top: build.py imports this module on every run
    with tempfile.TemporaryDirectory(prefix=f"landing-{sport_id}-") as tmp:
        demo_root = preview_root.write_root(sport_id, Path(tmp) / "root", root)
        league, problems = load_league(demo_root / LEAGUE_FILE, sports_root=demo_root / "sports", root=demo_root)
        if league is None:
            return None, problems
        league = replace(league, sample_data=True)
        data = load_data(demo_root, league, league.sport_def, today=today, data_dir=demo_root / "data")
        problems = problems + data.problems
        if has_errors(problems):
            return None, problems
        output, found = compute(league, data, data_dir=demo_root / "data", sport_preview=league.sport_def.name)
        return output, problems + found


# ------------------------------------------------------------------ landing.json

def build_page(league: League, words: dict, root: Path = ROOT, *, today=None) -> tuple[dict | None, list[Problem]]:
    """landing.json for a league with `landing_page: true` and checked `words` (read_words). Builds every demo league
    (about two seconds each). Returns (the page data, problems); the data is None when a demo does not build."""
    ids = list(league.sport_previews)
    blurbs, problems = read_blurbs(ids, root / "sports")
    sports, layouts = [], []
    for sport_id in ids:
        output, found = build_demo(sport_id, root, today=today)
        problems += with_file(found, f"the {sport_id} demo league")
        if output is None or has_errors(found):
            return None, problems
        sport = _window(sport_id, output, blurbs[sport_id])
        sport = {"id": sport_id, "name": sport["name"], "blurb": sport["blurb"], "url": f"/{sport_id}/",
                 "demo_label": words["demo_label"].replace("{name}", sport["name"]),
                 "league_name": sport["league_name"], "layout": sport["layout"], "window": sport["window"]}
        sports.append(sport)
        if sport["layout"] != LANDING_LAYOUT and sport["layout"] not in layouts:
            layouts.append(sport["layout"])
    footer_links = [{"label": f"{s['name']} demo", "url": s["url"]} for s in sports]
    footer_links += [{"label": link["label"], "url": link["url"]} for link in words["links"]]
    page = {
        "shell": {"name": words["name"], "short_name": words["name"], "code": words["code"].upper(),
                  "layout": LANDING_LAYOUT, "tagline": words["tagline"], "lang": league.lang,
                  "search_engines": league.search_engines, "footer_name": words["name"], "footer_line": "",
                  "nav": words["nav"], "footer_links": footer_links, "labels": dict(SHELL_LABELS),
                  "extra_layouts": layouts},
        "active": {"sample_mode": False, "preview": False},
        "intro": {"eyebrow": words["eyebrow"], "title": words["title"], "text": words["intro"]},
        "links": words["links"], "features_title": words["features_title"], "features": words["features"],
        "copy_note": words["copy_note"],
        "sports": sports,
        "coming_soon": words["coming_soon"],
    }
    return page, problems


# ------------------------------------------------------------------ the Jekyll overlay

def exclude_list(config_yml: Path) -> list[str]:
    """The `exclude` list of _config.yml (Jekyll replaces a list when it merges configs, so the overlay repeats it)."""
    raw, _ = read_yaml(config_yml, config_yml.name) if config_yml.is_file() else (None, [])
    items = raw.get("exclude") if isinstance(raw, dict) else None
    return [str(i) for i in items] if isinstance(items, list) else []


def overlay_text(on: bool, config_yml: Path | None = None) -> str:
    """The text of _config.landing.yml. Off: the one line `landing_page: false`. On: the landing page flag, `exclude`
    (_config.yml's list plus the league's own pages, minus landing/), an empty `include` and no output for the
    four collections, so the root holds the landing page and 404.html only."""
    if not on:
        return "landing_page: false\n"
    excluded = [e for e in exclude_list(config_yml) if e.rstrip("/") != "landing"] if config_yml else []
    excluded += [p for p in LEAGUE_PAGES if p not in excluded]
    lines = ["# Written by scripts/build.py while league.yml says landing_page: true (never edit by hand): the root of the",
             "# site is the landing page and 404.html; the league's own pages are left out of this build.",
             "landing_page: true", "exclude:"]
    lines += [f"  - {json.dumps(item)}" for item in excluded]
    lines += ["include: []", "collections:"]
    lines += [f"  {name}:\n    output: false" for name in COLLECTIONS]
    return "\n".join(lines) + "\n"


def write_overlay(out_root: Path, on: bool, config_yml: Path | None = None) -> Path:
    """Write _config.landing.yml into `out_root` (only when the text changed, so its date stays put)."""
    path = Path(out_root) / OVERLAY_FILE
    text = overlay_text(on, config_yml)
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8", newline="")
    return path


# ------------------------------------------------------------------ command line

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="landing.py", description="Print the landing page's data (landing.json).")
    parser.add_argument("--out", type=Path, metavar="FILE", help="write the JSON here instead of printing it")
    args = parser.parse_args(argv)
    league, problems = load_league()
    words, found = read_words(league) if league else (None, [])
    if league is None or words is None:
        from scripts.core.problems import format_human
        print(format_human(problems + found), file=sys.stderr)
        return 1
    page, found = build_page(league, words)
    if page is None:
        from scripts.core.problems import format_human
        print(format_human(found), file=sys.stderr)
        return 1
    text = json.dumps(page, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
