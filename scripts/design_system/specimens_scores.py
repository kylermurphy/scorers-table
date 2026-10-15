"""Specimens for the 'Scores' group (docs/design.md, "Part anatomy > Scores").

Parts, in page order:
    result-card    Result card: rows (`--tie`), compact line score (`--lines`)
    game-board     Result card `--hero` ("Game of the week" digit board; Scoreboard only)
    final-panel    Final panel `.st-final` (top of a game page), line score inside or beside it
    line-score     Line score: 4 shapes (quarters, ends, periods, innings) x `--card` / `--full`
    event-log      Hockey scoring summary `.st-events` + penalties `.st-table`
    roster         Curling lineups `.st-roster`
    game-tables    Stat tables on game pages (box score, game in numbers, skaters, goalies, batting)

Every piece of text and every number comes from `sample.LEAGUES[sport]` (results, featured, game,
labels).  Nothing is invented here: where a mockup has no data for a state (for example a hockey
line score with a highlighted period) the state is simply not shown for that sport.

Markup conventions added to the anatomy (each is explained in the parts-scores notes):
    .st-line-scroll        the scroll box around a line-score table (role=region + tabindex=0 only
                           when it is not inside a link)
    .st-line-score__team / __total / __extra / __open / __n      cells and the circled number wrapper
    .st-legend__key--won|mark|blank|limit|x                       legend keys
    .st-final__head / __body / __foot / __title / __meta          the two halves of the final panel
    .st-team-heading, .st-facts, .st-top-scorer, .st-table--box|numbers
"""
from __future__ import annotations

from . import sample
from .model import Ctx, Part, chip, esc, team_by_id

SHAPE = {"basketball": "quarters", "curling": "ends", "hockey": "periods", "slopitch": "innings"}
SHAPE_WORD = {
    "quarters": "Points by quarter",
    "ends": "Points by end",
    "periods": "Goals by period",
    "innings": "Runs by inning",
}
MARK_WORD = {"ends": "stolen end", "innings": "run limit", "quarters": "biggest quarter", "periods": "highlight"}
VOID_WORD = {"ends": "not played", "innings": "not needed"}
CHEVRON = '<span class="st-chevron" aria-hidden="true"> ›</span>'


def pad(html: str) -> str:
    return f'<div class="ds-pad">{html}</div>'


def tm(L: dict, tid: str) -> dict:
    return team_by_id(L, tid)


def dash(a, b) -> str:
    return f"{a}–{b}"


def hammer(label: str | None = "Hammer", size: int = 10) -> str:
    aria = f'role="img" aria-label="{esc(label)}"' if label else 'aria-hidden="true"'
    return (
        f'<svg class="st-hammer" width="{size}" height="{size}" viewBox="0 0 10 10" {aria} focusable="false">'
        '<circle class="st-hammer__ring" cx="5" cy="5" r="5"/>'
        '<circle class="st-hammer__mid" cx="5" cy="5" r="3.3"/>'
        '<circle class="st-hammer__core" cx="5" cy="5" r="2.1"/></svg>'
    )


def legend_item(kind: str, text: str, mark: str = "") -> str:
    if kind == "hammer":
        key = hammer(None, 12)
    elif kind in ("limit", "x"):
        mark = mark or "X"
        key = f'<span class="st-legend__key st-legend__key--{kind}" aria-hidden="true">{esc(mark)}</span>'
    else:
        key = f'<span class="st-legend__key st-legend__key--{kind}" aria-hidden="true"></span>'
    return f'<span class="st-legend__item">{key}<span>{esc(text)}</span></span>'


def legend(items: list[str], stack: bool = False, full: bool = False) -> str:
    """full=True: the legend of a full-size line score (its keys get the cells' 2 px frame)."""
    cls = "st-legend" + (" st-legend--stack" if stack else "") + (" st-legend--full" if full else "")
    return f'<div class="{cls}">{"".join(items)}</div>'


def legend_kind(text: str) -> str:
    low = text.lower()
    if "hammer" in low:
        return "hammer"
    if "stolen" in low:
        return "mark"
    if "blank" in low:
        return "blank"
    return "x"


# --------------------------------------------------------------------------- line score

def scroll_box(table: str, label: str, region: bool) -> str:
    attrs = f' role="region" aria-label="{esc(label)}" tabindex="0"' if region else ""
    return f'<div class="st-line-scroll"{attrs}>{table}</div>'


def line_score(ctx: Ctx, size: str, *, shape: str, rows: list[dict], labels: list[str], total_label: str,
               extra_label: str | None = None, corner: str = "Team", won=None, marks=None, blanks=(),
               hammers=None, hammer_first=None, open_idx=None, use_code: bool = False,
               region: bool = True) -> str:
    """One `table.st-line-score` in its scroll box.

    rows:   [{id, cells[int|None], total, extra, winner True|False|None}]
    won:    {team id: {1-based periods}}   is-won   (scored end; biggest quarter)
    marks:  {team id: {1-based periods}}   is-mark  (stolen end; run-limit inning)
    blanks: {1-based periods}              is-blank on header + cells (full size only)
    hammers:      {team id: {1-based ends}} hammer svg in the cell (full)
    hammer_first: team id with the hammer in end 1: hammer svg after the name (card)
    open_idx:     0-based index of the open inning (full)
    """
    L = ctx.league
    won = won or {}
    marks = marks or {}
    hammers = hammers or {}
    cls = f"st-line-score st-line-score--{shape} st-line-score--{size}"
    cap_bits = ", ".join(f'{tm(L, r["id"])["name"]} {r["total"]}' for r in rows)
    out = [f'<table class="{cls}"><caption class="st-visually-hidden">{esc(SHAPE_WORD[shape])}: {esc(cap_bits)}</caption>']
    # head
    head = [f'<th scope="col" class="st-line-score__team">{esc(corner)}</th>']
    for i, lab in enumerate(labels, start=1):
        c = []
        if i in blanks:
            c.append("is-blank")
        if open_idx is not None and i - 1 == open_idx:
            c.append("is-open")
        attr = f' class="{" ".join(c)}"' if c else ""
        inner = esc(lab)
        if open_idx is not None and i - 1 == open_idx:
            inner += '<span class="st-line-score__open">open</span>'
        if i in blanks:
            inner += '<span class="st-visually-hidden"> (blank end)</span>'
        head.append(f'<th scope="col"{attr}>{inner}</th>')
    head.append(f'<th scope="col" class="st-line-score__total">{esc(total_label)}</th>')
    if extra_label:
        head.append(f'<th scope="col" class="st-line-score__extra">{esc(extra_label)}</th>')
    out.append(f'<thead><tr>{"".join(head)}</tr></thead><tbody>')
    for r in rows:
        t = tm(L, r["id"])
        rc = {True: ' class="is-winner"', False: ' class="is-loser"', None: ""}[r.get("winner")]
        if use_code and t.get("code_in_mockup"):
            name = f'<abbr title="{esc(t["name"])}">{esc(t["code"])}</abbr>'
        else:
            name = esc(t["name"])
        h = hammer("Hammer in end 1") if hammer_first == r["id"] else ""
        cells = [f'<th scope="row" class="st-line-score__team">{chip(t, "sm")}'
                 f'<span class="st-line-score__name">{name}</span>{h}</th>']
        for i, v in enumerate(r["cells"], start=1):
            c, inner = [], ""
            if v is None:
                c.append("is-void")
                inner = (f'<span aria-hidden="true">X</span>'
                         f'<span class="st-visually-hidden">{VOID_WORD.get(shape, "not played")}</span>')
            else:
                inner = esc(v)
                if i in won.get(r["id"], ()):
                    c.append("is-won")
                    if shape in ("quarters", "periods"):
                        inner += f'<span class="st-visually-hidden"> ({MARK_WORD[shape]})</span>'
                if i in marks.get(r["id"], ()):
                    c.append("is-mark")
                    inner = (f'<span class="st-line-score__n">{esc(v)}</span>'
                             f'<span class="st-visually-hidden"> ({MARK_WORD[shape]})</span>')
            if i in blanks:
                c.append("is-blank")
            if open_idx is not None and i - 1 == open_idx:
                c.append("is-open")
            if i in hammers.get(r["id"], ()):
                inner += hammer("Hammer")
            attr = f' class="{" ".join(c)}"' if c else ""
            cells.append(f"<td{attr}>{inner}</td>")
        cells.append(f'<td class="st-line-score__total">{esc(r["total"])}</td>')
        if extra_label:
            cells.append(f'<td class="st-line-score__extra">{esc(r["extra"])}</td>')
        out.append(f"<tr{rc}>{''.join(cells)}</tr>")
    out.append("</tbody></table>")
    label = f"{SHAPE_WORD[shape]}, scrolls sideways"
    return scroll_box("".join(out), label, region)


def _scored(cells_by_team: dict) -> dict:
    return {k: {i for i, v in enumerate(c, start=1) if v} for k, c in cells_by_team.items()}


def ls_from_result(ctx: Ctx, r: dict, size: str = "card", *, region: bool = False, use_code: bool = False) -> str:
    """Compact line score of a result (sample `results` entry)."""
    L = ctx.league
    shape = SHAPE[ctx.sport]
    ids = [r["home"], r["away"]]
    ps = r["period_scores"]
    n = len(ps[ids[0]])
    has_hits = "hits" in r
    rows = [{
        "id": i, "cells": ps[i], "total": r["scores"][i],
        "extra": r["hits"][i] if has_hits else None,
        "winner": None if r["winner"] is None else (r["winner"] == i),
    } for i in ids]
    won = _scored(ps) if shape == "ends" else {}
    marks = r.get("stolen") if shape == "ends" else (r.get("limit_innings") if shape == "innings" else {})
    marks = {k: set(v) for k, v in (marks or {}).items()}
    return line_score(
        ctx, size, shape=shape, rows=rows, labels=L["period_labels"][:n], total_label=L["total_label"],
        extra_label="H" if has_hits else None, corner="End" if shape == "ends" else "Team",
        won=won, marks=marks, hammer_first=r.get("hammer") if shape == "ends" else None,
        use_code=use_code, region=region)


def ls_from_game(ctx: Ctx, size: str = "full", *, region: bool = True) -> str:
    """The game page's line score (sample `game.line_score`)."""
    L = ctx.league
    g = L["game"]
    ls = g["line_score"]
    shape = SHAPE[ctx.sport]
    n = len(ls["rows"][0]["cells"])
    cols = ls["columns"]
    labels, open_idx = [], None
    for i, c in enumerate(cols[:n]):
        if c.endswith(" open"):
            open_idx = i
            c = c[:-5]
        labels.append(c)
    winners = {t["team"]: t["winner"] for t in g["final"]["teams"]}
    rows = [{
        "id": r["team"], "cells": r["cells"], "total": r["total"], "extra": r.get("hits"),
        "winner": winners.get(r["team"]),
    } for r in ls["rows"]]
    won = marks = hammers = None
    blanks = ()
    if shape == "ends":
        won = _scored({r["team"]: r["cells"] for r in ls["rows"]})
        marks = {k: set(v) for k, v in ls["stolen"].items()}
        hammers = {k: set(v) for k, v in ls["hammer_by_end"].items()}
        blanks = set(ls["blank_ends"])
    elif shape == "innings":
        marks = {k: set(v) for k, v in ls["limit_innings"].items()}
    elif shape == "quarters":
        won = {k: {v} for k, v in ls["highlight"]["periods"].items()}
    return line_score(
        ctx, size, shape=shape, rows=rows, labels=labels, total_label=cols[n],
        extra_label=cols[n + 1] if len(cols) > n + 1 else None, corner=ls["corner_label"],
        won=won, marks=marks, blanks=blanks, hammers=hammers, open_idx=open_idx,
        use_code=(shape == "ends"), region=region)


# --------------------------------------------------------------------------- result card

def _results(L: dict) -> list[dict]:
    return L["results"]


def _bold(text: str, strong: str | None) -> str:
    out = esc(text)
    if strong and esc(strong) in out:
        out = out.replace(esc(strong), f"<b>{esc(strong)}</b>", 1)
    return out


def card_foot(ctx: Ctx, r: dict) -> str:
    """Foot of a result card; the wording follows each mockup."""
    link_text = r["link_label"].replace(" ›", "")
    link = f'<span class="st-result-card__link">{esc(link_text)}{CHEVRON}</span>'
    status = r["status"]
    if ctx.layout == "classic":
        bits = [status] + (["Tie"] if r["tie"] else [])
        if ctx.sport == "curling" and r["meta"]:
            bits += [p for p in r["meta"].split(" · ") if p != r["time"]]
        note = " · ".join(esc(b) for b in bits)
    elif ctx.sport == "curling":
        note = esc(r["meta"] or "")
    elif ctx.sport == "hockey":
        note = f"{esc(status)} · {_bold(r['note'], r['note_strong'])}"
    else:
        note = _bold(r["note"], r["note_strong"])
        if ctx.layout == "scoreboard":
            note = f"{esc(status)} · {note}"
    return (f'<span class="st-result-card__foot"><span class="st-result-card__note">{note}</span>{link}</span>')


def result_card(ctx: Ctx, r: dict, lines: bool = False) -> str:
    L = ctx.league
    cls = "st-card st-result-card"
    if lines:
        cls += " st-result-card--lines"
    if r["tie"]:
        cls += " st-result-card--tie"
    head = ""
    if ctx.sport == "slopitch" and lines:
        bits = [r["status"]] + (["Tie"] if r["tie"] else []) + ([r["meta"]] if r["meta"] else [])
        head = f'<span class="st-result-card__head">{esc(" · ".join(bits))}</span>'
    if lines:
        body = ls_from_result(ctx, r, "card", region=False, use_code=False)
    else:
        rows = []
        for tid in (r["home"], r["away"]):
            t = tm(L, tid)
            win = r["winner"] == tid
            rows.append(
                f'<span class="st-result-card__team{" is-winner" if win else ""}">{chip(t)}'
                f'<span class="st-result-card__name">{esc(t["name"])}</span>'
                f'<span class="st-result-card__score">{r["scores"][tid]}</span></span>')
        body = "".join(rows)
    return f'<a class="{cls}" href="#">{head}{body}{card_foot(ctx, r)}</a>'


def render_result_cards(ctx: Ctx) -> str:
    L = ctx.league
    res = _results(L)
    out = []
    if ctx.sport == "curling":
        out.append(legend([legend_item(legend_kind(t), t) for t in L["results_legend"]]))
        out.append('<div class="st-list">' + "".join(result_card(ctx, r, True) for r in res) + "</div>")
    elif ctx.sport == "slopitch":
        out.append('<div class="st-list">' + "".join(result_card(ctx, r, True) for r in res) + "</div>")
        note = L["results_legend"][0]
        # "5 = inning ended at the 5-run limit. X = not needed."
        first, rest = note.split(" = ", 1)
        out.append(f'<p class="st-note"><span class="st-legend__key st-legend__key--limit st-legend__key--text">{esc(first)}</span>'
                   f' = {esc(rest)}</p>')
    else:
        out.append('<div class="st-list">' + "".join(result_card(ctx, r) for r in res) + "</div>")
        first = next(r for r in res if r["period_scores"])
        out.append('<p class="st-note" style="margin:.75rem 0 .5rem">The same game with its line score (<code>--lines</code>):</p>')
        out.append('<div class="st-list">' + result_card(ctx, first, True) + "</div>")
    return pad("".join(out))


# --------------------------------------------------------------------------- hero ("game of the week")

def _hero_result(L: dict) -> dict:
    feat = L.get("featured")
    rid = feat["result"] if feat else _results(L)[0]["id"]
    return next(r for r in _results(L) if r["id"] == rid)


def render_hero(ctx: Ctx) -> str:
    L = ctx.league
    r = _hero_result(L)
    feat = L.get("featured")
    lab = feat["label"] if feat else "Game of the week"
    date = feat["date"] if feat else f'{r["status"]} · {r["date"]}'
    ids = [r["home"], r["away"]]
    cols = []
    for tid in ids:
        t = tm(L, tid)
        cols.append(
            f'<div class="st-final__team{" is-winner" if r["winner"] == tid else ""}">'
            f'<span class="st-final__name">{chip(t)}<span>{esc(t["name"])}</span></span>'
            f'<span class="st-final__record">{esc(t["record"])}</span></div>')
    nums = "".join(
        f'<span class="st-final__num{" is-dim" if (r["winner"] and r["winner"] != tid) else ""}">{r["scores"][tid]}</span>'
        for tid in ids)
    score = (f'<div class="st-final__score"><span class="st-visually-hidden">Final score: </span>{nums}</div>')
    head = f'<div class="st-final__head st-final__head--board">{cols[0]}{score}{cols[1]}</div>'
    shape = SHAPE[ctx.sport]
    if shape in ("quarters", "periods"):
        ps = r["period_scores"]
        tiles = []
        for i, lab_p in enumerate(L["period_labels"][: len(ps[ids[0]])]):
            pair = "".join(
                f'<span class="{"is-dim" if (r["winner"] and r["winner"] != tid) else "is-lead"}">{ps[tid][i]}</span>'
                for tid in ids)
            tiles.append(f'<li class="st-period-tile"><span class="st-period-tile__label">{esc(lab_p)}</span>'
                         f'<span class="st-period-tile__pair">{pair}</span></li>')
        mid = (f'<ol class="st-result-card__periods" aria-label="Score by period">{"".join(tiles)}</ol>')
    else:
        mid = ls_from_result(ctx, r, "card", region=True, use_code=True)
    note = r["note_long"] or r["note"] or ""
    top = f'<p class="st-result-card__top">{_bold(note, r["note_strong"])}</p>' if note else ""
    btn = esc(r["link_label"].replace(" ›", ""))
    inner = (
        f'<p class="st-result-card__eyebrow"><span>{esc(lab)}</span><span>{esc(date)}</span></p>'
        f'{head}{mid}{top}<a class="st-button" href="#">{btn}</a>')
    return pad(f'<div class="st-result-card st-result-card--hero">{inner}</div>')


# --------------------------------------------------------------------------- final panel

def final_head(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    f = g["final"]
    status = f["label"]
    parts = []
    if status:
        parts.append(f'<p class="st-final__status">{esc(status)}</p>')
    if f["sub"]:
        parts.append(f'<p class="st-final__sub">{esc(f["sub"])}</p>')
    teams, nums = [], []
    for t in f["teams"]:
        tt = tm(L, t["team"])
        badge = ""
        if t.get("result") == "WIN":
            badge = ' <span class="st-badge st-badge--win">WIN</span>'
        rec = t.get("record_text") or t["record"]
        teams.append(
            f'<div class="st-final__team{" is-winner" if t["winner"] else ""}">'
            f'<span class="st-final__name">{chip(tt, "lg")}<span>{esc(tt["name"])}{badge}</span></span>'
            f'<span class="st-final__record">{esc(rec)}</span></div>')
        nums.append(f'<span class="st-final__num {"is-first" if not nums else "is-second"}{"" if t["winner"] else " is-dim"}">{t["score"]}</span>')
    score = (f'<div class="st-final__score"><span class="st-visually-hidden">Final score: </span>'
             f'{nums[0]}<span class="st-final__sep" aria-hidden="true">–</span>{nums[1]}</div>')
    return f'<div class="st-final__head">{"".join(parts)}{teams[0]}{score}{teams[1]}</div>'


def final_foot(ctx: Ctx) -> str:
    L = ctx.league
    ls = L["game"]["line_score"]
    s = ctx.sport
    if s == "basketball":
        return f'<div class="st-final__foot">{legend([legend_item("won", ls["note"])], full=True)}</div>'
    if s == "curling":
        note = esc(ls["note"])
        team = tm(L, ls["first_end_hammer"])["name"]
        note = note.replace(esc(team), f"<b>{esc(team)}</b>", 1)
        items = [legend_item(legend_kind(t), t) for t in ls["legend"]]
        return f'<div class="st-final__foot"><p class="st-final__note">{note}</p>{legend(items, full=True)}</div>'
    if s == "hockey":
        gl = " · ".join(f"<b>{esc(p['label'])}</b>" for p in ls["foot_goalies"])
        ids = [r["team"] for r in ls["rows"]]
        pim = dash(*[ls["foot_pim"][i] for i in ids])
        return (f'<div class="st-final__foot st-final__foot--split"><span>Goalies: {gl}</span>'
                f'<span>PIM {pim}</span></div>')
    items = []
    for n in ls["notes"]:
        items.append(legend_item("limit" if n["kind"] == "limit" else "x", n["text"], n["mark"]))
    return f'<div class="st-final__foot">{legend(items, stack=True, full=True)}</div>'


def render_final(ctx: Ctx) -> str:
    L = ctx.league
    ls = L["game"]["line_score"]
    title = ""
    if ls.get("title") or ls.get("meta"):
        t = f'<h2 class="st-final__title">{esc(ls["title"])}</h2>' if ls.get("title") else ""
        m = f'<span class="st-final__meta">{esc(ls["meta"])}</span>' if ls.get("meta") else ""
        title = f'<div class="st-final__titlerow">{t}{m}</div>'
    body = f'<div class="st-final__body">{title}{ls_from_game(ctx, "full", region=True)}{final_foot(ctx)}</div>'
    return pad(f'<section class="st-final" aria-label="Final score">{final_head(ctx)}{body}</section>')


# --------------------------------------------------------------------------- line score part

def render_line_score(ctx: Ctx) -> str:
    L = ctx.league
    r = L["results"][0]
    out = [
        '<p class="st-label">Full size (game page)</p>',
        f'<div class="st-card" style="padding:.75rem .5rem .25rem">{ls_from_game(ctx, "full", region=True)}</div>',
        '<p class="st-label" style="margin-top:1.25rem">Card size (inside a result card)</p>',
        f'<div class="st-card" style="padding:.75rem .875rem">{ls_from_result(ctx, r, "card", region=True)}</div>',
    ]
    if ctx.sport == "curling":
        # the last draw: a stolen end, a blank end and two unplayed ends (X)
        r2 = L["results"][-1]
        out.append(f'<div class="st-card" style="padding:.75rem .875rem;margin-top:.625rem">{ls_from_result(ctx, r2, "card", region=True)}</div>')
    ls = L["game"]["line_score"]
    leg = []
    if ctx.sport == "basketball":
        leg = [legend_item("won", ls["note"])]
    elif ctx.sport == "curling":
        leg = [legend_item(legend_kind(t), t) for t in ls["legend"]]
    elif ctx.sport == "slopitch":
        leg = [legend_item("limit" if n["kind"] == "limit" else "x", n["text"], n["mark"]) for n in ls["notes"]]
    if leg:
        out.append(f'<div style="margin-top:.75rem">{legend(leg, stack=ctx.sport == "slopitch", full=True)}</div>')
    return pad("".join(out))


# --------------------------------------------------------------------------- event log

def render_events(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    scoring = next(s for s in g["sections"] if s["kind"] == "scoring")
    pen = next(s for s in g["sections"] if s["kind"] == "penalties")
    out = [f'<div class="st-section__head"><h2 class="st-section__title">{esc(scoring["title"])}</h2></div>',
           '<div class="st-events">']
    for p in scoring["periods"]:
        tally = " · ".join(f'{tm(L, tid)["code"]} {n}' for tid, n in p["tally"].items())
        out.append(f'<section class="st-events__group"><h3 class="st-events__head"><span>{esc(p["label"])}</span>'
                   f'<span class="st-events__tally">{esc(tally)}</span></h3><ol class="st-events__list">')
        for e in p["goals"]:
            t = tm(L, e["team"])
            gwg = ' <span class="st-badge">GWG</span>' if e["gwg"] else ""
            if e["assists"]:
                lab = "Assist" if len(e["assists"]) == 1 else "Assists"
                sub = f'{lab}: ' + ", ".join(esc(a["label"]) for a in e["assists"])
            else:
                sub = "Unassisted"
            out.append(
                f'<li class="st-event"><span class="st-event__time">{esc(e["time"])}</span>'
                f'<span class="st-event__team">{chip(t)}<abbr class="st-team-code" title="{esc(t["name"])}">{esc(t["code"])}</abbr></span>'
                f'<span class="st-event__who"><span class="st-event__name">{esc(e["scorer"]["label"])}{gwg}</span>'
                f'<span class="st-event__sub">{sub}</span></span>'
                f'<span class="st-event__score">{dash(*e["score"])}</span></li>')
        out.append("</ol></section>")
    out.append("</div>")
    out.append(f'<p class="st-note">{esc(scoring["note"])}</p>')
    # penalties
    out.append(f'<div class="st-section__head" style="margin-top:1.625rem"><h2 class="st-section__title">{esc(pen["title"])}</h2></div>')
    cols = pen["columns"]
    th = "".join(f'<th scope="col"{" class=is-left" if i in (2, 3) else ""}>{esc(c)}</th>' for i, c in enumerate(cols))
    rows = []
    for r in pen["rows"]:
        t = tm(L, r["team"])
        rows.append(
            f'<tr><td>{r["period"]}</td><td>{esc(r["time"])}</td>'
            f'<td class="is-left st-table__strong">{chip(t, "sm")}'
            f'<abbr class="st-team-code" title="{esc(t["name"])}">{esc(t["code"])}</abbr>'
            f'{esc(r["player"]["label"])}</td><td class="is-left">{esc(r["infraction"])}</td><td>{r["minutes"]}</td></tr>')
    out.append(
        '<div class="st-table-wrap" role="region" aria-label="Penalties, scrolls sideways" tabindex="0">'
        f'<table class="st-table st-table--events"><caption class="st-visually-hidden">Penalties</caption>'
        f'<thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    leg = [f'<span class="st-legend__item">{chip(tm(L, t), "sm")}<span>{esc(tm(L, t)["name"])}</span></span>'
           for t in pen["legend_teams"]]
    out.append(f'<div style="margin-top:.5rem">{legend(leg)}</div>')
    return pad("".join(out))


# --------------------------------------------------------------------------- roster

def render_roster(ctx: Ctx) -> str:
    L = ctx.league
    sec = next(s for s in L["game"]["sections"] if s["kind"] == "lineups")
    out = [f'<div class="st-section__head"><h2 class="st-section__title">{esc(sec["title"])}</h2></div>',
           '<div class="st-list">']
    for t in sec["teams"]:
        tt = tm(L, t["team"])
        link = t["link_label"].replace(tt["name"] + " ", "")
        rows = []
        for r in t["rows"]:
            name = esc(r["player"]["label"])
            if r["spare_for"]:
                name += (f' <span class="st-badge st-badge--outline">Spare</span>'
                         f' <span class="st-roster__for">for {esc(r["spare_for"]["label"])}</span>')
            cls = "st-roster__name is-key" if r["emphasis"] else "st-roster__name"
            rows.append(f'<li class="st-roster__row"><span class="st-roster__role">{esc(r["position"])}</span>'
                        f'<span class="{cls}">{name}</span></li>')
        out.append(
            f'<div class="st-roster"><a class="st-roster__head" href="#">{chip(tt, "lg")}'
            f'<span class="st-roster__team">{esc(tt["name"])}</span>'
            f'<span class="st-roster__link">{esc(link.replace(" ›", ""))}{CHEVRON}</span>'
            '<span class="st-visually-hidden"> rink page</span></a>'
            f'<ol class="st-roster__list">{"".join(rows)}</ol></div>')
    out.append("</div>")
    out.append(f'<p class="st-note">{esc(sec["note"])}</p>')
    return pad("".join(out))


# --------------------------------------------------------------------------- game-page tables

def table_wrap(label: str, table: str) -> str:
    return (f'<div class="st-table-wrap" role="region" aria-label="{esc(label)}, scrolls sideways" tabindex="0">'
            f'{table}</div>')


def th_col(c: dict) -> str:
    cls = ' class="is-key"' if c.get("key_col") else ""
    return f'<th scope="col"{cls}><abbr title="{esc(c["title"])}">{esc(c["label"])}</abbr></th>'


def team_heading(L: dict, tid: str, score=None, title: str | None = None, small: bool = False) -> str:
    t = tm(L, tid)
    cls = "st-team-heading st-team-heading--sm" if small else "st-team-heading"
    sc = f'<span class="st-team-heading__score">{score}</span>' if score is not None else ""
    tag = "h3" if small else "h2"
    return (f'<{tag} class="{cls}">{chip(t, "lg")}<span class="st-team-heading__name">{esc(title or t["name"])}</span>'
            f'{sc}</{tag}>')


def player_link(p: dict, full: bool = True) -> str:
    return f'<a class="st-player" href="#">{esc(p["label"] if full else p["name"])}</a>'


def basketball_tables(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    ts = g["top_scorer"]
    p = ts["player"]
    out = [
        '<div class="st-top-scorer">'
        f'<div class="st-top-scorer__main"><p class="st-top-scorer__label">{esc(ts["label"])}</p>'
        f'<a class="st-top-scorer__name" href="#">{esc(p["label"])}</a>'
        f'<p class="st-top-scorer__detail">{esc(ts["detail"])}</p></div>'
        f'<p class="st-top-scorer__value"><span class="st-top-scorer__num">{ts["value"]}</span>'
        f'<span class="st-top-scorer__unit">{esc(ts["unit"])}</span></p></div>']
    for b in g["box_scores"]:
        t = tm(L, b["team"])
        cols = b["columns"]
        head = (f'<th scope="col">{esc(b["number_label"])}</th><th scope="col" class="is-left">{esc(b["player_label"])}</th>'
                + "".join(th_col(c) for c in cols))
        rows = "".join(
            f'<tr><td>{r["player"]["number"]}</td><td class="is-left">{player_link(r["player"], False)}</td>'
            f'<td class="is-key">{r["pts"]}</td><td>{r["ftm"]}-{r["fta"]}</td><td>{r["pf"]}</td></tr>'
            for r in b["rows"])
        tt = b["totals"]
        foot = (f'<tfoot><tr><td></td><td class="is-left">{esc(tt["label"])}</td><td class="is-key">{tt["pts"]}</td>'
                f'<td>{tt["ftm"]}-{tt["fta"]}</td><td>{tt["pf"]}</td></tr></tfoot>')
        table = (f'<table class="st-table st-table--box"><caption class="st-visually-hidden">{esc(t["name"])} box score</caption>'
                 f'<thead><tr>{head}</tr></thead><tbody>{rows}</tbody>{foot}</table>')
        out.append(f'<section class="st-game-block">{team_heading(L, b["team"], b["score"])}'
                   f'{table_wrap(t["name"] + " box score", table)}'
                   f'<p class="st-note">{esc(b["note"])}</p></section>')
    out += [f'<p class="st-note">{esc(n)}</p>' for n in g["footnotes"]]
    return "".join(out)


def curling_tables(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    sec = next(s for s in g["sections"] if s["kind"] == "numbers")
    ids = [t["team"] for t in g["final"]["teams"]]
    th = "".join(
        f'<th scope="col">{chip(tm(L, i), "sm")}<abbr title="{esc(tm(L, i)["name"])}">{esc(tm(L, i)["code"])}</abbr></th>'
        for i in ids)
    rows = []
    for r in sec["rows"]:
        tds = []
        for i in ids:
            cls = []
            if r["emphasis"] == i:
                cls.append("is-key")
                if r["style"] == "stolen":
                    cls.append("is-hot")
            c = f' class="{" ".join(cls)}"' if cls else ""
            tds.append(f"<td{c}>{esc(r['values'][i])}</td>")
        rows.append(f'<tr><td>{esc(r["label"])}</td>{"".join(tds)}</tr>')
    table = (f'<table class="st-table st-table--numbers"><caption class="st-visually-hidden">{esc(sec["title"])}</caption>'
             f'<thead><tr><th scope="col">{esc(sec["corner_label"])}</th>{th}</tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>')
    return (f'<section class="st-game-block"><div class="st-section__head"><h2 class="st-section__title">{esc(sec["title"])}</h2></div>'
            f'{table_wrap(sec["title"], table)}<p class="st-note">{esc(sec["note"])}</p></section>')


def hockey_tables(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    gl = next(s for s in g["sections"] if s["kind"] == "goalies")
    sk = next(s for s in g["sections"] if s["kind"] == "skaters")
    # goalies
    rows = []
    for r in gl["rows"]:
        t = tm(L, r["team"])
        rows.append(f'<tr><td>{player_link(r["player"])}</td><td class="is-left">{chip(t, "sm")} {esc(t["name"])}</td>'
                    f'<td class="st-table__strong">{esc(r["result"])}</td><td class="st-table__big">{r["ga"]}</td></tr>')
    th = "".join(f'<th scope="col"{" class=is-left" if i == 1 else ""}>{esc(c)}</th>' for i, c in enumerate(gl["columns"]))
    gtable = (f'<table class="st-table"><caption class="st-visually-hidden">{esc(gl["title"])}</caption>'
              f'<thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>')
    out = [f'<section class="st-game-block"><div class="st-section__head"><h2 class="st-section__title">{esc(gl["title"])}</h2></div>'
           f'{table_wrap(gl["title"], gtable)}<p class="st-note">{esc(gl["note"])}</p></section>']
    # skaters
    out.append(f'<section class="st-game-block"><div class="st-section__head"><h2 class="st-section__title">{esc(sk["title"])}</h2></div>'
               f'<p class="st-note st-note--intro">{esc(sk["intro"])}</p>')
    for tb in sk["teams"]:
        t = tm(L, tb["team"])
        body = "".join(
            f'<tr><td>{player_link(r["player"])}</td><td>{r["g"]}</td><td>{r["a"]}</td><td class="is-key">{r["pts"]}</td><td>{r["pim"]}</td></tr>'
            for r in tb["rows"])
        tt = tb["total"]
        foot = (f'<tfoot><tr><td>Total</td><td>{tt["g"]}</td><td>{tt["a"]}</td><td class="is-key">{tt["pts"]}</td><td>{tt["pim"]}</td></tr></tfoot>')
        table = (f'<table class="st-table"><caption class="st-visually-hidden">{esc(t["name"])} skaters</caption>'
                 f'<thead><tr><th scope="col">Player</th>{"".join(th_col(c) for c in sk["columns"])}</tr></thead>'
                 f'<tbody>{body}</tbody>{foot}</table>')
        out.append(f'<div class="st-game-block">{team_heading(L, tb["team"], small=True)}{table_wrap(t["name"] + " skaters", table)}</div>')
    out.append("</section>")
    return "".join(out)


def slopitch_tables(ctx: Ctx) -> str:
    L = ctx.league
    g = L["game"]
    facts = next(s for s in g["sections"] if s["kind"] == "facts")
    rows = []
    for r in facts["rows"]:
        if "groups" in r:
            parts = []
            for grp in r["groups"]:
                names = ", ".join(esc(p["label"]) for p in grp["players"])
                parts.append(f'{names} <span class="st-facts__team">({esc(tm(L, grp["team"])["name"])})</span>')
            val = "; ".join(parts)
        else:
            val = "; ".join(f'{esc(tm(L, x["team"])["name"])} {x["count"]} ({esc(", ".join(x["innings"]))})' for x in r["limit"])
        rows.append(f'<div class="st-facts__row"><dt class="st-facts__label">{esc(r["label"])}</dt><dd class="st-facts__value">{val}</dd></div>')
    out = [f'<dl class="st-facts">{"".join(rows)}</dl>']
    for b in (s for s in g["sections"] if s["kind"] == "batting"):
        t = tm(L, b["team"])
        head = (f'<th scope="col">{esc(b["order_label"])}</th><th scope="col" class="is-left">{esc(b["player_label"])}</th>'
                + "".join(th_col(c) for c in b["columns"]))
        body = "".join(
            f'<tr><td>{r["order"]}</td><td class="is-left">{player_link(r["player"], False)}</td>'
            f'<td>{r["ab"]}</td><td>{r["r"]}</td><td>{r["h"]}</td><td>{r["rbi"]}</td><td>{r["hr"]}</td></tr>'
            for r in b["rows"])
        tt = b["totals"]
        foot = (f'<tfoot><tr><td colspan="2" class="is-left">{esc(tt["label"])}</td><td>{tt["ab"]}</td><td>{tt["r"]}</td>'
                f'<td>{tt["h"]}</td><td>{tt["rbi"]}</td><td>{tt["hr"]}</td></tr></tfoot>')
        table = (f'<table class="st-table st-table--box"><caption class="st-visually-hidden">{esc(b["title"])}</caption>'
                 f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody>{foot}</table>')
        out.append(f'<section class="st-game-block">{team_heading(L, b["team"], title=b["title"])}{table_wrap(b["title"], table)}</section>')
    out += [f'<p class="st-note">{esc(n)}</p>' for n in g["footnotes"]]
    return "".join(out)


def render_tables(ctx: Ctx) -> str:
    fn = {"basketball": basketball_tables, "curling": curling_tables,
          "hockey": hockey_tables, "slopitch": slopitch_tables}[ctx.sport]
    return pad(fn(ctx))


PARTS = [
    Part(id="result-card", title="Result card", group="Scores", render=render_result_cards, sports="all",
         note="a.st-result-card: the whole card is the link. Rows (basketball, hockey) or --lines with a compact line "
              "score (curling, slopitch); --tie for a tie. The last card of basketball and hockey shows the --lines form."),
    Part(id="result-card-hero", title="Result card, hero (game of the week)", group="Scores", render=render_hero,
         sports="all", layouts=("scoreboard",),
         note="Scoreboard's digit board: --hero holds the board, the per-period tiles (quarters, periods) or a "
              "line-score table (ends, innings), the top performer and a Box score button."),
    Part(id="final-panel", title="Final panel", group="Scores", render=render_final, sports="all",
         note="Top of a game page: both teams, the big score with the loser dimmed, record, and the line score "
              "inside it (basketball, classic, curling, hockey, scoreboard) or as its own card below (slo-pitch)."),
    Part(id="line-score", title="Line score", group="Scores", render=render_line_score, sports="all",
         note="Four shapes (quarters, ends, periods, innings) in two sizes (--full, --card), every sport in every "
              "layout. Cell states: is-won, is-mark, is-blank, is-void, is-open; hammer svg; legend."),
    Part(id="event-log", title="Event log and penalties", group="Scores", render=render_events, sports=("hockey",),
         note="Hockey's scoring summary (.st-events) and penalty table, shown in every layout."),
    Part(id="roster", title="Roster (lineups)", group="Scores", render=render_roster, sports=("curling",),
         note="Curling lineups in throwing order, skip in bold, Spare badge; shown in every layout."),
    Part(id="game-tables", title="Game-page stat tables", group="Scores", render=render_tables, sports="layout",
         note="Box score + top scorer (basketball), the game in numbers (curling), goalies and skaters (hockey), "
              "facts and batting (slo-pitch), in the layouts that show them."),
]
