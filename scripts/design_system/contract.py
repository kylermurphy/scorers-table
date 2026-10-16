"""The stage 3 sample leagues in the shapes of the stage 4 computed JSON (docs/stage-4-spec.md 4.1).

`build(sport, layout)` turns one sample league, as one layout shows it, into the files `_data/computed/`
holds (league, active, teams, standings, schedule, results, games, players, leaders) plus `case`, a small
file of fixture values for the test pages (the strings a page layout would build: the game page's title
block, the section headings; never read by an include). The parity test (tests/test_parity.py) renders
the Jekyll includes with this data and compares them with the stage 3 specimens, so these shapes are
proved able to carry every mockup before any real sport writes a line of code.

Where the abridged table in the spec leaves a field open, the choice made here is the one the includes
read; docs/design.md ("Stage 4 includes") lists every such field. Rules for this module:

* It converts, it does not compute: every number and string the specimens print arrives ready to print.
* Layout-dependent text (labels, the next-game foot, the card foot) is resolved for the layout asked for,
  as `build.py` resolves `labels_by_layout` and the sport's display hints.
* A function of (sport, layout) only; no clock, no randomness.

    python -m scripts.design_system.contract OUT_DIR       # writes OUT_DIR/<layout>--<sport>/<name>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):                      # run as a file: put the repo root on the path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.design_system import sample  # noqa: E402
from scripts.design_system.model import SPORTS  # noqa: E402

SHAPE = {"basketball": "quarters", "curling": "ends", "hockey": "periods", "slopitch": "innings"}
SHAPE_WORD = {"quarters": "Points by quarter", "ends": "Points by end", "periods": "Goals by period",
              "innings": "Runs by inning"}
MARK_WORD = {"ends": "stolen end", "innings": "run limit", "quarters": "biggest quarter", "periods": "highlight"}
VOID_WORD = {"ends": "not played", "innings": "not needed"}

# What the sport hands the core as `display` hints (spec 3.2). `card_head` is the one hint added here.
DISPLAY = {
    "basketball": {"card": "rows", "card_foot": "note", "surface": "label", "card_head": ""},
    "curling": {"card": "lines", "card_foot": "meta", "surface": "label", "card_head": ""},
    "hockey": {"card": "rows", "card_foot": "status_note", "surface": "sub", "card_head": ""},
    "slopitch": {"card": "lines", "card_foot": "note", "surface": "label", "card_head": "status_surface"},
}

NAV_KEYS = {"Home": ("home", "/"), "Schedule": ("schedule", "/schedule/"), "Stats": ("stats", "/stats/"),
            "Teams": ("teams", "/teams/"), "Archive": ("archive", "/archive/")}
FOOTER_URLS = {"Teams": "/teams/", "Past seasons": "/archive/", "League rules": "/rules/",
               "Contact": "mailto:contact@example.org"}

CUSTOM_CHIPS = [("Navy", "#1D3A6E"), ("Black", "#000000"), ("Green", "#2F6B3A"), ("Brown", "#7A4A1E"),
                ("Purple", "#5B3A8C"), ("Red", "#9E1B32"), ("Gold", "#F2A900"), ("Yellow", "#FFC233")]


def cases() -> list[tuple[str, str]]:
    """Every (layout, sport) pair any specimen is rendered for: the six layouts x the four sports."""
    return [(lay["id"], sport) for lay in sample.LAYOUTS for sport in SPORTS]


def layout_meta(layout: str) -> dict:
    return sample.LAYOUT_BY_ID[layout]


# ----------------------------------------------------------------------------- small helpers

def tid(team_id: str) -> str:
    return team_id.replace("_", "-")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def plain_link(label: str) -> str:
    """The sample keeps the mockup's chevron in link labels; the markup draws its own."""
    return label.replace(" ›", "")


def team_of(L: dict, team_id: str) -> dict:
    return sample.team(L["sport"], team_id)


def labels_for(L: dict, layout: str) -> dict:
    over = L.get("layout_labels", {}).get(layout, {})
    labels = {**L["labels"], **over}
    st = L["standings"]
    labels["team"] = st["team_label_general"] if layout_meta(layout)["kind"] == "general" else st["team_label"]
    labels["final"] = "Final"
    labels["tie"] = "Tie"
    labels["featured"] = (L.get("featured") or {}).get("label", "Game of the week")
    return labels


# ----------------------------------------------------------------------------- league, active

def league_json(L: dict, layout: str) -> dict:
    return {
        "name": L["name"], "short_name": L["short_name"], "code": L["code"],
        "sport": L["sport"], "sport_name": L["sport"].title(), "layout": layout,
        "colour": None, "colour_dark": None, "logo": None,
        "tagline": L["tagline"], "footer_line": L["footer_line"], "footer_name": L["footer_name"],
        "contact_href": FOOTER_URLS["Contact"], "search_engines": False, "lang": "en",
        "nav": [{"label": n, "url": NAV_KEYS[n][1], "key": NAV_KEYS[n][0]} for n in L["nav"]],
        "footer_links": [{"label": n, "url": FOOTER_URLS[n]} for n in L["footer_links"]],
        "labels": labels_for(L, layout),
        "words": {"surface": L["surface_word"], "period": {"one": L["period_word"], "many": L["period_word"] + "s",
                                                           "short": L["period_word"][0]}},
        "display": dict(DISPLAY[L["sport"]]),
        "placeholders": [],
    }


def active_json() -> dict:
    return {"season": "2026-27", "sample_mode": True, "archive": [], "today": "2026-11-20", "preview": False}


# ----------------------------------------------------------------------------- teams, standings

def _rank_of(L: dict, team_id: str) -> int:
    return [r["team"] for r in L["standings"]["rows"]].index(team_id) + 1


def _pts(L: dict, team_id: str):
    row = next(r for r in L["standings"]["rows"] if r["team"] == team_id)
    return row["values"].get("PTS")


def teams_json(L: dict) -> dict:
    out = {}
    for t in L["teams"]:
        pts = _pts(L, t["id"])
        out[tid(t["id"])] = {
            "id": tid(t["id"]), "name": t["name"], "code": t["code"], "slot": t["slot"], "colour": None,
            "url": f"/teams/{tid(t['id'])}/", "rank": _rank_of(L, t["id"]), "record": t["record"],
            "points": None if pts is None else str(pts),
            "sub": f"Skip {t['skip']}" if L["sport"] == "curling" and t.get("skip") else None,
            "players": [], "results": [], "upcoming": [], "calendar": None,
        }
    return out


def _race(L: dict, row: dict) -> dict:
    """The numbers of one row of the race (Scoreboard standings): bar width, big value, sub line."""
    st = L["standings"]
    v = row["values"]
    if st["bar"]["basis"] == "win_pct":
        pct = float(v["PCT"]) * 100
    else:
        pct = v["PTS"] / st["bar"]["max"] * 100
    if "PTS" in v:
        value, unit = str(v["PTS"]), " points"
        sub = team_of(L, row["team"])["record"]
    else:
        value, unit = f'{v["W"]}–{v["L"]}', ""
        sub = str(v["DIFF"]) + ("" if v["GB"] == "—" else f' · {v["GB"]} GB')
    return {"pct": f"{pct:.1f}", "value": value, "unit": unit, "sub": sub}


def standings_json(L: dict) -> dict:
    st = L["standings"]
    cols = [{"key": c["key"].lower(), "label": c["label"], "title": c["title"], "key_col": c["key_col"]}
            for c in st["columns"]]
    rows = []
    for i, row in enumerate(st["rows"], start=1):
        rows.append({
            "rank": i, "team": tid(row["team"]),
            "values": {k.lower(): v for k, v in row["values"].items()},
            "display": {k.lower(): str(v) for k, v in row["values"].items()},
            "record": team_of(L, row["team"])["record"], "tiebreak": None,
            "race": _race(L, row),
        })
    basis = "win_pct" if st["bar"]["basis"] == "win_pct" else "points"
    return {"columns": cols, "rows": rows, "note": L["points_note"], "tiebreak_note": None, "through": None,
            "race": {"basis": basis, "max": st["bar"].get("max")}}


# ----------------------------------------------------------------------------- line scores

def _legend_kind(text: str) -> str:
    low = text.lower()
    if "hammer" in low:
        return "hammer"
    if "stolen" in low:
        return "mark"
    if "blank" in low:
        return "blank"
    return "x"


def _legend_item(kind: str, text: str, mark: str = "") -> dict:
    item = {"kind": kind, "text": text}
    if kind in ("limit", "x"):
        item["mark"] = mark or "X"
    return item


def _scored(cells: list) -> set:
    return {i for i, v in enumerate(cells, start=1) if v}


def _line_score(L: dict, ids: list[str], side_cells: dict, totals: dict, *, labels: list[str], corner: str,
                total_label: str, extra_label: str | None = None, extras: dict | None = None,
                won: dict | None = None, marks: dict | None = None, blanks=(), open_idx: int | None = None,
                hammers: dict | None = None, hammer_first: str | None = None) -> dict:
    """One line_score object (spec 3.4) for the two teams `ids` (first-listed first)."""
    shape = SHAPE[L["sport"]]
    won, marks, hammers = won or {}, marks or {}, hammers or {}
    columns = []
    for i, lab in enumerate(labels):
        col = {"label": lab}
        if open_idx is not None and i == open_idx:
            col["open"] = True
        if (i + 1) in blanks:
            col["blank"] = True
        columns.append(col)
    rows = {}
    for side, team_id in zip(("home", "away"), ids):
        cells = []
        for i, v in enumerate(side_cells[team_id], start=1):
            cell: dict = {"v": v}
            if v is None:
                cell["void"] = True
            else:
                if i in won.get(team_id, ()):
                    cell["won"] = True
                if i in marks.get(team_id, ()):
                    cell["mark"] = True
            if i in hammers.get(team_id, ()):
                cell["hammer"] = True
            cells.append(cell)
        rows[side] = {"cells": cells, "total": totals[team_id],
                      "extra": None if extras is None else extras[team_id],
                      "hammer_first": hammer_first == team_id}
    return {
        "shape": shape, "corner": corner, "total_label": total_label, "extra_label": extra_label,
        "columns": columns, "rows": rows, "caption": SHAPE_WORD[shape],
        "won_word": MARK_WORD[shape] if shape == "quarters" else None,
        "mark_word": MARK_WORD[shape], "void_word": VOID_WORD.get(shape, "not played"),
        "blank_word": "blank end", "hammer_word": "Hammer",
        "title": None, "meta": None, "legend": [], "legend_stack": False,
        "note": None, "note_strong": None, "split": None,
    }


def card_line_score(L: dict, r: dict) -> dict | None:
    """The compact line score of a result (what a result card and the hero hold)."""
    ps = r["period_scores"]
    if ps is None:
        return None
    shape = SHAPE[L["sport"]]
    ids = [r["home"], r["away"]]
    n = len(ps[ids[0]])
    has_hits = "hits" in r
    marks = r.get("stolen") if shape == "ends" else (r.get("limit_innings") if shape == "innings" else {})
    marks = {k: set(v) for k, v in (marks or {}).items()}
    won = {k: _scored(c) for k, c in ps.items()} if shape == "ends" else {}
    return _line_score(
        L, ids, ps, r["scores"], labels=L["period_labels"][:n],
        corner="End" if shape == "ends" else "Team", total_label=L["total_label"],
        extra_label="H" if has_hits else None, extras=r["hits"] if has_hits else None,
        won=won, marks=marks, hammer_first=r.get("hammer") if shape == "ends" else None)


def game_line_score(L: dict, g: dict) -> dict:
    """The game page's line score (full size) with its title, legend and foot."""
    ls = g["line_score"]
    shape = SHAPE[L["sport"]]
    ids = [r["team"] for r in ls["rows"]]
    n = len(ls["rows"][0]["cells"])
    cols = ls["columns"]
    labels, open_idx = [], None
    for i, c in enumerate(cols[:n]):
        if c.endswith(" open"):
            open_idx = i
            c = c[:-5]
        labels.append(c)
    won = marks = hammers = None
    blanks: set = set()
    if shape == "ends":
        won = {r["team"]: _scored(r["cells"]) for r in ls["rows"]}
        marks = {k: set(v) for k, v in ls["stolen"].items()}
        hammers = {k: set(v) for k, v in ls["hammer_by_end"].items()}
        blanks = set(ls["blank_ends"])
    elif shape == "innings":
        marks = {k: set(v) for k, v in ls["limit_innings"].items()}
    elif shape == "quarters":
        won = {k: {v} for k, v in ls["highlight"]["periods"].items()}
    has_extra = len(cols) > n + 1
    out = _line_score(
        L, ids, {r["team"]: r["cells"] for r in ls["rows"]}, {r["team"]: r["total"] for r in ls["rows"]},
        labels=labels, corner=ls["corner_label"], total_label=cols[n],
        extra_label=cols[n + 1] if has_extra else None,
        extras={r["team"]: r.get("hits") for r in ls["rows"]} if has_extra else None,
        won=won, marks=marks, blanks=blanks, open_idx=open_idx, hammers=hammers)
    out["title"], out["meta"] = ls.get("title"), ls.get("meta")
    sport = L["sport"]
    if sport == "basketball":
        out["legend"] = [_legend_item("won", ls["note"])]
    elif sport == "curling":
        team = team_of(L, ls["first_end_hammer"])["name"]
        out["note"], out["note_strong"] = ls["note"], team
        out["legend"] = [_legend_item(_legend_kind(t), t) for t in ls["legend"]]
    elif sport == "hockey":
        gl: list = []
        for i, p in enumerate(ls["foot_goalies"]):
            if i:
                gl.append({"t": " · "})
            gl.append({"t": p["label"], "b": True})
        pim = "–".join(str(ls["foot_pim"][i]) for i in ids)
        out["split"] = [[{"t": "Goalies: "}] + gl, [{"t": f"PIM {pim}"}]]
    else:
        out["legend"] = [_legend_item("limit" if n_["kind"] == "limit" else "x", n_["text"], n_["mark"])
                         for n_ in ls["notes"]]
        out["legend_stack"] = True
    return out


# ----------------------------------------------------------------------------- games

def _surface_label(L: dict, surface) -> str | None:
    return f'{L["surface_word"]} {surface}' if surface and L["surface_word"] else None


def _side(L: dict, team_id: str, score, result: str, line: str | None = None, badge: str = "") -> dict:
    t = team_of(L, team_id)
    side = {"team": tid(team_id), "name": t["name"], "code": t["code"], "slot": t["slot"], "colour": None,
            "score": score, "result": result, "record": t["record"], "badge": badge}
    if line:
        side["record_line"] = line
    return side


def _result_of(r: dict, team_id: str) -> str:
    if r["winner"] is None:
        return "tie"
    return "win" if r["winner"] == team_id else "loss"


def _player_id(label_or_name: str) -> str:
    return slug(label_or_name)


def players_json(L: dict) -> dict:
    """The people the sample names (the box score and the leaders link to them)."""
    out = {}

    def add(p: dict, team_id: str) -> None:
        pid = _player_id(p["name"])
        out.setdefault(pid, {"id": pid, "name": p["name"], "label": p["label"], "number": p["number"],
                             "team": tid(team_id), "team_name": team_of(L, team_id)["name"], "sub": False,
                             "position": None, "url": f"/players/{pid}/"})

    if L["sport"] == "basketball":
        for box in L["game"]["box_scores"]:
            for row in box["rows"]:
                add(row["player"], box["team"])
    ld = L["leaders"]
    for t in ld["tiles"]:
        if t["person"] is not None:
            add(t["person"], t["team"])
    for lst in ld["lists"]:
        for r in lst["rows"]:
            if r["person"] is not None:
                add(r["person"], r["team"])
    return out


def _basketball_blocks(L: dict) -> list[dict]:
    g = L["game"]
    ts = g["top_scorer"]
    blocks = [{"type": "top_performer", "label": ts["label"], "player": _player_id(ts["player"]["name"]),
               "side": next(side for side, box in zip(("home", "away"), g["box_scores"]) if box["team"] == ts["team"]),
               "value": ts["value"], "unit": ts["unit"], "detail": ts["detail"]}]
    for side, box in zip(("home", "away"), g["box_scores"]):
        t = team_of(L, box["team"])
        cols = [{"key": "pts", "label": "PTS", "title": "Points", "key_col": True},
                {"key": "ft", "label": "FTM-FTA", "title": "Free throws made-attempted"},
                {"key": "pf", "label": "PF", "title": "Personal fouls"}]
        rows = [{"player": _player_id(r["player"]["name"]), "num": r["player"]["number"],
                 "cells": {"pts": str(r["pts"]), "ft": f'{r["ftm"]}-{r["fta"]}', "pf": str(r["pf"])}}
                for r in box["rows"]]
        tt = box["totals"]
        blocks.append({
            "type": "stat_table", "title": None, "side": side, "caption": f'{t["name"]} box score',
            "number_col": True, "number_label": box["number_label"], "player_label": box["player_label"],
            "columns": cols, "rows": rows,
            "totals": {"label": tt["label"], "cells": {"pts": str(tt["pts"]), "ft": f'{tt["ftm"]}-{tt["fta"]}',
                                                       "pf": str(tt["pf"])}},
            "note": box["note"]})
    blocks += [{"type": "note", "text": n} for n in g["footnotes"]]
    return blocks


def games_json(L: dict, layout: str) -> dict:
    sport = L["sport"]
    gm = L["game"]
    feat = L.get("featured")
    out = {}
    for r in L["results"]:
        a, b = r["home"], r["away"]
        is_game = r["game"] is not None
        final = {"status": None, "sub": None}
        line_a = line_b = None
        badges = {a: "", b: ""}
        if is_game:
            f = gm["final"]
            final = {"status": f["label"], "sub": f["sub"]}
            for t in f["teams"]:
                if t.get("result") == "WIN":
                    badges[t["team"]] = "WIN"
            line_a, line_b = (next(t for t in f["teams"] if t["team"] == x).get("record_text") for x in (a, b))
        card = {"note": r["note"], "strong": r["note_strong"], "link_label": plain_link(r["link_label"]),
                "meta": [p for p in (r["meta"] or "").split(" · ") if p], "note_long": r["note_long"]}
        cls = card_line_score(L, r)
        if cls is not None:
            card["line_score"] = cls
        full = game_line_score(L, gm) if is_game else None
        if sport == "basketball" and is_game:
            blocks = _basketball_blocks(L)
        else:
            blocks = []
        hero_date = (feat["date"].split(" · ", 1)[1] if feat and feat["result"] == r["id"] else r["date"])
        out[r["id"]] = {
            "id": r["id"], "url": f"/games/{r['id']}/", "type": "regular", "round": None,
            "day_label": L["results_header"]["meta"].split(" · ")[0],
            "date_short": hero_date, "date_long": r["date"], "time_display": r["time"], "venue": L["venue"],
            "surface_label": _surface_label(L, r["surface"]),
            "home": _side(L, a, r["scores"][a], _result_of(r, a), line_a, badges[a]),
            "away": _side(L, b, r["scores"][b], _result_of(r, b), line_b, badges[b]),
            "tie": r["tie"], "forfeit": None, "decided_in": "regulation", "status": r["status"],
            "summary": final["sub"], "final": final, "notes": [], "photo_url": None, "standings_points": {},
            "line_score": full if full is not None else cls, "card": card, "tiles": None, "blocks": blocks,
        }
    return out


# ----------------------------------------------------------------------------- schedule, results

def _schedule_row(L: dict, gid: str, home: str, away: str, surface, time, *, played=False, score=None,
                  winner=None) -> dict:
    return {
        "id": gid, "url": f"/games/{gid}/", "time_display": time, "surface": surface,
        "surface_label": _surface_label(L, surface), "home": tid(home), "away": tid(away),
        "home_name": team_of(L, home)["name"], "away_name": team_of(L, away)["name"],
        "status": "played" if played else "scheduled", "moved_from_display": None, "round": None,
        "played": played, "score": score or {"home": None, "away": None}, "winner": winner,
    }


def _foot(L: dict, layout: str) -> str:
    """The next-game foot, as the layout words it (`bye` and Scoreboard rules: docs/design.md)."""
    nd = L["next_day"]
    if layout == "scoreboard":
        if nd.get("foot_scoreboard"):
            return nd["foot_scoreboard"]
        return "" if nd["bye"] else nd["foot"]
    if layout == "classic" and nd.get("foot_classic"):
        return nd["foot_classic"]
    return nd["foot"]


def schedule_json(L: dict, layout: str) -> dict:
    nd = L["next_day"]
    played_rows = []
    for r in L["results"]:
        win = None if r["winner"] is None else ("home" if r["winner"] == r["home"] else "away")
        played_rows.append(_schedule_row(
            L, r["id"], r["home"], r["away"], r["surface"], r["time"], played=True,
            score={"home": r["scores"][r["home"]], "away": r["scores"][r["away"]]}, winner=win))
    hdr = L["results_header"]["meta"]
    latest = {
        "n": 1, "label": hdr.split(" · ")[0], "date": "2026-11-12", "date_short": hdr.split(" · ")[1],
        "date_long": L["results"][0]["date"], "type": "regular", "venues": [L["venue"]], "state": "played",
        "games": played_rows, "byes": [tid(L["bye"])] if L["bye"] else [],
    }
    groups, flat = [], []
    for gi, g in enumerate(nd["groups"], start=1):
        rows = [_schedule_row(L, f"next-{gi}-{ri}", x["home"], x["away"], x["surface"], x["time"])
                for ri, x in enumerate(g["rows"], start=1)]
        flat += rows
        groups.append({"time_label": g["time_label"], "games": rows})
    foot_link = ({"label": nd["foot_link"], "url": "/schedule/"} if nd.get("foot_link") else None)
    nxt = {
        "n": 2, "label": nd["eyebrow"], "date": "2026-11-19", "date_short": nd["label_short"],
        "date_long": nd["label"], "type": "regular", "venues": [L["venue"]], "state": "upcoming",
        "games": flat, "byes": [tid(nd["bye"])] if nd["bye"] else [],
        # fields the next-game panel prints (docs/design.md, "Stage 4 includes")
        "eyebrow": nd["eyebrow"],
        "where": " · ".join(x for x in (nd["where"], nd.get("week_label"), nd.get("where_note")) if x),
        "foot": _foot(L, layout), "foot_link": foot_link, "groups": groups,
    }
    strip = bool((layout == "classic" and nd.get("foot_classic")) or
                 (layout == "scoreboard" and nd.get("foot_scoreboard")))
    return {"days": [latest, nxt], "latest": 1, "next": 2, "all_times_pm": strip}


def results_json(L: dict) -> list:
    return [{"day": 1, "games": [r["id"] for r in L["results"]]}]


# ----------------------------------------------------------------------------- leaders

def _shown(item: dict, layout: str) -> bool:
    only = item.get("only_layouts")
    return only is None or layout in only


def _columns(cols) -> list | None:
    if not cols:
        return None
    return [{"key": c["key"].lower(), "label": c["label"], "title": c["title"], "key_col": c["key_col"]}
            for c in cols]


def leaders_json(L: dict, layout: str) -> dict:
    ld = L["leaders"]
    boards = []
    tiles = [t for t in ld["tiles"] if _shown(t, layout)]
    for i, t in enumerate(tiles):
        person = t["person"] is not None
        meta = t["meta"]
        if person:
            prefix = team_of(L, t["team"])["name"] + " · "
            assert meta.startswith(prefix), (t["key"], meta)
            meta = meta[len(prefix):]
        boards.append({
            "id": t["key"], "label": t["label"], "of": "player" if person else "team",
            "group": (t.get("group") or "player").lower(), "group_label": t.get("group"), "stat": t["key"], "tile": True, "list": False,
            "edge": t["edge"] or ("hot" if i == 0 else "accent"),
            "min": {"note": ld.get("note")}, "unranked": [], "columns": None, "title": t["label"],
            "unit": None, "first_row_in_tile": False,
            "rows": [{"rank": 1, "player": _player_id(t["person"]["name"]) if person else None,
                      "team": tid(t["team"]), "label": t["name"], "value": t["value"], "display": t["value"],
                      "detail": meta, "cells": None}],
        })
    for lst in [x for x in ld["lists"] if _shown(x, layout)]:
        rows = []
        for r in lst["rows"]:
            person = r["person"] is not None
            rows.append({
                "rank": r["rank"], "player": _player_id(r["person"]["name"]) if person else None,
                "team": tid(r["team"]), "label": r["name"], "value": r["value"], "display": r["value"],
                "detail": r["detail"],
                "cells": {k.lower(): str(v) for k, v in r["values"].items()} if r["values"] else None})
        boards.append({
            "id": lst["key"], "label": lst["title"], "of": "team" if rows and rows[0]["player"] is None else "player",
            "group": "player", "group_label": None, "stat": lst["key"], "tile": False, "list": True, "edge": None,
            "min": {"note": lst.get("note")}, "unranked": [], "columns": _columns(lst["columns"]),
            "title": lst["title"], "title_board": lst.get("title_scoreboard"), "unit": lst.get("unit"),
            "first_row_in_tile": lst["first_row_in_tile"], "rows": rows})
    return {"boards": boards, "table": None}


# ----------------------------------------------------------------------------- case (test fixtures)

def case_json(L: dict, layout: str) -> dict:
    sport = L["sport"]
    gm = L["game"]
    h = gm["header"]
    labels = labels_for(L, layout)
    legend_items: list = []
    note_parts = None
    if sport == "curling":
        variant = "curling"
        legend_items = [_legend_item(_legend_kind(t), t) for t in L["results_legend"]]
    elif sport == "slopitch":
        variant = "slopitch"
        first, rest = L["results_legend"][0].split(" = ", 1)
        note_parts = {"key": first, "rest": rest}
    else:
        variant = "rows"
    feat = L.get("featured")
    hero_id = feat["result"] if feat else L["results"][0]["id"]
    first_card = next(r["id"] for r in L["results"] if r["period_scores"])
    team_card = dict(teams_json(L)[tid(L["teams"][0]["id"])])
    team_card.update({"colour": "#1D3A6E", "sub": None, "points": None})
    return {
        "variant": variant, "legend": legend_items, "note_parts": note_parts,
        "game_id": gm["id"], "hero_id": hero_id, "first_lines_id": first_card,
        "page_title": {"back_label": gm["back_label"], "eyebrow": h["eyebrow"], "title": h["title"],
                      "sub": h["subline"], "sub2": h["venue_line"]},
        "results_header_meta": L["results_header"]["meta"],
        "results_title": labels["results"] if layout != "scoreboard" else (feat or {}).get("label", labels["results"]),
        "custom_chips": [{"name": n, "hex": hx, "colour": hx, "slot": 1} for n, hx in CUSTOM_CHIPS],
        "custom_card_team": team_card,
    }


# ----------------------------------------------------------------------------- everything

def build(sport: str, layout: str) -> dict:
    L = sample.LEAGUES[sport]
    return {
        "league": league_json(L, layout),
        "active": active_json(),
        "teams": teams_json(L),
        "standings": standings_json(L),
        "schedule": schedule_json(L, layout),
        "results": results_json(L),
        "games": games_json(L, layout),
        "players": players_json(L),
        "leaders": leaders_json(L, layout),
        "case": case_json(L, layout),
    }


def write(out_dir: Path) -> list[Path]:
    """Write OUT_DIR/<layout>--<sport>/<name>.json for every case; returns the folders."""
    folders = []
    for layout, sport in cases():
        folder = Path(out_dir) / f"{layout}--{sport}"
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in build(sport, layout).items():
            (folder / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        folders.append(folder)
    return folders


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for f in write(Path(sys.argv[1])):
        print(f)
