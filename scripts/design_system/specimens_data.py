"""Specimens for the Data group: standings (table and race), leaders, game row,
next-game panel, team card.  Anatomy: docs/design.md, "Data".  CSS: assets/css/parts-data.css.

Everything is filled from scripts/design_system/sample.py; nothing is invented here.
Stage 4 rewrites each function as a Jekyll include; the class names are the contract.

Decisions that the specimens make (the notes file explains each in full):

* Standings is ONE part (`standings`) whose render branches on ctx.layout: the Scoreboard
  gets "The race" (`.st-race`), every other layout gets the table.  One part, not two,
  because the generator's League-colour section looks `standings` up by id and renders it
  in every layout, so a Scoreboard frame there must show the race too.  The Scoreboard's
  full-standings table (the page the race links to) is a second part, `standings-table`,
  with `layouts=("scoreboard",)`.
* Which leader tiles / lists show in a layout follows the sample's `only_layouts` markers.
  A tile without an `edge` in the sample gets one by position (first `hot`, then
  `accent`): the edge is presentation, and the layout decides whether it paints a top edge
  or only colours the number.
* Game rows read the layout and sport, not the markup: the surface is a letter tile
  (curling layout), a text label (Classic), an icon + "Diamond 1" (slo-pitch layout), a
  tag "D1" (Scoreboard) or a second line under the time (hockey).  Times lose " PM"
  where the mockup's foot note says "All times PM" (Classic curling, Scoreboard slo-pitch).
"""
from __future__ import annotations

from .model import Ctx, Part, chip, esc, team_by_id

# --------------------------------------------------------------------------- helpers


def lab(ctx: Ctx, key: str) -> str:
    """A section name: the league's default, or the layout's own rename (sample.layout_labels)."""
    over = ctx.league.get("layout_labels", {}).get(ctx.layout, {})
    return over.get(key) or ctx.league["labels"][key]


def tname(ctx: Ctx, team_id: str) -> str:
    return team_by_id(ctx.league, team_id)["name"]


def tslot(ctx: Ctx, team_id: str) -> int:
    return team_by_id(ctx.league, team_id)["slot"]


def section_head(title: str, link_label: str | None) -> str:
    link = f'<a class="st-section__aside" href="#">{esc(link_label)}</a>' if link_label else ""
    return (f'<div class="st-section__head"><h2 class="st-section__title">{esc(title)}</h2>{link}</div>')


def is_scoreboard(ctx: Ctx) -> bool:
    return ctx.layout == "scoreboard"


def pad(inner: str) -> str:
    return f'<div class="ds-pad">{inner}</div>'


# --------------------------------------------------------------------------- standings


def _table_head(ctx: Ctx, st: dict) -> str:
    general = ctx.layout_meta["kind"] == "general"
    first = st["team_label_general"] if general else st["team_label"]
    cells = [f'<th scope="col" class="is-left">{esc(first)}</th>']
    for col in st["columns"]:
        key = " is-key" if col["key_col"] else ""
        cells.append(
            f'<th scope="col" class="st-num{key}"><abbr title="{esc(col["title"])}">{esc(col["label"])}</abbr></th>'
        )
    return "<thead><tr>" + "".join(cells) + "</tr></thead>"


def standings_table_markup(ctx: Ctx) -> str:
    st = ctx.league["standings"]
    body = []
    for rank, row in enumerate(st["rows"], start=1):
        t = team_by_id(ctx.league, row["team"])
        cells = [
            f'<th scope="row"><span class="st-rank">{rank}</span>'
            f'{chip(t, "sm")}<span class="st-table__team">{esc(t["name"])}</span></th>'
        ]
        for col in st["columns"]:
            key = ' class="is-key"' if col["key_col"] else ""
            cells.append(f'<td{key}>{esc(row["values"][col["key"]])}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    caption = f'{lab(ctx, "standings")}, {ctx.league["name"]}'
    return (
        f'<div class="st-table-wrap st-table-wrap--standings" role="region" '
        f'aria-label="{esc(lab(ctx, "standings"))} table" tabindex="0">'
        f'<table class="st-table st-table--standings">'
        f'<caption class="st-visually-hidden">{esc(caption)}</caption>'
        f'{_table_head(ctx, st)}<tbody>{"".join(body)}</tbody></table></div>'
    )


def _race_numbers(ctx: Ctx, row: dict) -> tuple[float, str, str, str]:
    """(bar %, right-hand value, sub text, hidden unit word) for one race row."""
    st = ctx.league["standings"]
    v = row["values"]
    basis = st["bar"]["basis"]
    if basis == "win_pct":
        pct = float(v["PCT"]) * 100
    else:
        pct = v["PTS"] / st["bar"]["max"] * 100
    if "PTS" in v:
        value, unit = str(v["PTS"]), " points"
        sub = team_by_id(ctx.league, row["team"])["record"]
    else:  # basketball: the record is the big number, the sub line is difference and games behind
        value, unit = f'{v["W"]}–{v["L"]}', ""
        sub = str(v["DIFF"]) + ("" if v["GB"] == "—" else f' · {v["GB"]} GB')
    return pct, value, sub, unit


def standings_race_markup(ctx: Ctx) -> str:
    st = ctx.league["standings"]
    items = []
    for rank, row in enumerate(st["rows"], start=1):
        pct, value, sub, unit = _race_numbers(ctx, row)
        lead = " st-race__row--lead" if rank == 1 else ""
        items.append(
            f'<li><a class="st-race__row{lead}" href="#">'
            f'<span class="st-race__rank">{rank}</span>'
            f'<span class="st-race__who"><span class="st-race__name">{esc(tname(ctx, row["team"]))}</span> '
            f'<span class="st-race__sub">{esc(sub)}</span>'
            f'<span class="st-race__bar" aria-hidden="true"><span class="st-race__fill" style="width:{pct:.1f}%"></span></span></span>'
            f'<span class="st-race__points">{esc(value)}'
            + (f'<span class="st-visually-hidden">{unit}</span>' if unit else "")
            + "</span></a></li>"
        )
    return f'<ol class="st-race" aria-label="{esc(lab(ctx, "standings"))}">{"".join(items)}</ol>'


def render_standings(ctx: Ctx) -> str:
    st = ctx.league["standings"]
    if is_scoreboard(ctx):
        bar = "win %" if st["bar"]["basis"] == "win_pct" else f'points out of {st["bar"]["max"]} possible'
        note = (
            f'Bar = {bar}. {esc(ctx.league["points_note"])} '
            f'<a href="#">{esc(lab(ctx, "full_table"))}</a>'
        )
        return pad(
            f'<section class="st-section">{section_head(lab(ctx, "standings"), None)}'
            f'{standings_race_markup(ctx)}<p class="st-note">{note}</p></section>'
        )
    return pad(
        f'<section class="st-section">{section_head(lab(ctx, "standings"), lab(ctx, "full_table"))}'
        f'{standings_table_markup(ctx)}<p class="st-note">{esc(ctx.league["points_note"])}</p></section>'
    )


def render_standings_table(ctx: Ctx) -> str:
    st = ctx.league["standings"]
    return pad(
        f'<section class="st-section">{section_head("Full standings", None)}'
        f'{standings_table_markup(ctx)}<p class="st-note">{esc(ctx.league["points_note"])}</p></section>'
    )


# --------------------------------------------------------------------------- leaders


def _shown(item: dict, layout: str) -> bool:
    only = item.get("only_layouts")
    return only is None or layout in only


def _tiles(ctx: Ctx) -> list[dict]:
    return [t for t in ctx.league["leaders"]["tiles"] if _shown(t, ctx.layout)]


def _lists(ctx: Ctx) -> list[dict]:
    return [l for l in ctx.league["leaders"]["lists"] if _shown(l, ctx.layout)]


def render_leader_tile(ctx: Ctx) -> str:
    ld = ctx.league["leaders"]
    tiles = _tiles(ctx)
    out = [f'<section class="st-section">{section_head(lab(ctx, "leaders"), lab(ctx, "all_stats"))}']
    groups: list[tuple[str | None, list[dict]]] = []
    for i, t in enumerate(tiles):  # keep the sample's order; a new group label starts a new grid
        g = t.get("group")
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append((i, t))
    for g, members in groups:
        if g:
            out.append(f'<p class="st-label st-leader-group">{esc(g)}</p>')
        cells = []
        for i, t in members:
            edge = t["edge"] or ("hot" if i == 0 else "accent")
            cells.append(
                f'<a class="st-leader-tile st-leader-tile--{edge}" href="#">'
                f'<span class="st-leader-tile__label">{esc(t["label"])}</span>'
                f'<span class="st-leader-tile__value">{esc(t["value"])}</span>'
                f'<span class="st-leader-tile__name">{esc(t["name"])}</span>'
                f'<span class="st-leader-tile__meta">{esc(t["meta"])}</span></a>'
            )
        out.append(f'<div class="st-leader-grid">{"".join(cells)}</div>')
    if ld.get("note"):
        out.append(f'<p class="st-note">{esc(ld["note"])}</p>')
    out.append("</section>")
    return pad("".join(out))


def _row_sub(ctx: Ctx, lst: dict, row: dict, with_values: bool) -> str:
    """Team name + detail (+ 'G, A' for a hockey row shown outside the hockey table)."""
    parts = []
    if row["person"] is not None:
        parts.append(tname(ctx, row["team"]))
    if row["detail"]:
        parts.append(row["detail"])
    if with_values and row["values"] and lst["columns"]:
        extra = [f'{row["values"][c["key"]]} {c["label"]}' for c in lst["columns"] if not c["key_col"]]
        parts.append(", ".join(extra))
    return " · ".join(parts)


def _hockey_table(ctx: Ctx, lst: dict) -> str:
    head = ['<th scope="col" class="is-left">Player</th>']
    for c in lst["columns"]:
        key = " is-key" if c["key_col"] else ""
        head.append(f'<th scope="col" class="st-num{key}"><abbr title="{esc(c["title"])}">{esc(c["label"])}</abbr></th>')
    body = []
    for row in lst["rows"]:
        first = " is-first" if row["rank"] == 1 else ""
        sub = _row_sub(ctx, lst, row, with_values=False)
        cells = [
            f'<th scope="row"><a class="st-leader-cell" href="#">'
            f'<span class="st-rank-chip{first}">{row["rank"]}</span>'
            f'<span class="st-leader-cell__who"><span class="st-leader-cell__name">{esc(row["name"])}</span>'
            f'<span class="st-leader-cell__sub">{esc(sub)}</span></span></a></th>'
        ]
        for c in lst["columns"]:
            key = ' class="is-key"' if c["key_col"] else ""
            cells.append(f'<td{key}>{esc(row["values"][c["key"]])}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<p class="st-label st-leader-group">{esc(lst["title"])}</p>'
        f'<div class="st-table-wrap" role="region" aria-label="{esc(lst["title"])} leaders" tabindex="0">'
        f'<table class="st-table st-table--leaders"><caption class="st-visually-hidden">{esc(lst["title"])} leaders</caption>'
        f'<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _leader_rows(ctx: Ctx, lst: dict) -> str:
    rows = lst["rows"]
    if lst["first_row_in_tile"]:
        rows = rows[1:]  # the tile above already shows rank 1
    unit = lst.get("unit")
    classic = ctx.layout == "classic"
    out = []
    for row in rows:
        first = " is-first" if row["rank"] == 1 else ""
        sub = _row_sub(ctx, lst, row, with_values=True)
        team = f' <span class="st-leader-row__team">{esc(sub)}</span>' if sub else ""
        unit_html = f'<span class="st-leader-row__unit">{esc(unit)}</span>' if unit and classic else ""
        out.append(
            f'<a class="st-leader-row" href="#"><span class="st-leader-row__rank{first}">{row["rank"]}</span>'
            f'<span class="st-leader-row__who"><span class="st-leader-row__name">{esc(row["name"])}</span>{team}</span>'
            f'<span class="st-leader-row__value">{esc(row["value"])}{unit_html}</span></a>'
        )
    title_cls = " st-visually-hidden" if classic else ""  # Classic: the section heading is the title
    note = f'<p class="st-note">{esc(lst["note"])}</p>' if lst.get("note") and not is_scoreboard(ctx) else ""
    return (
        f'<div class="st-leader-list"><h3 class="st-leader-list__title{title_cls}">{esc(lst["title"])}</h3>'
        f'{"".join(out)}</div>{note}'
    )


def _leader_board(ctx: Ctx, lst: dict) -> str:
    rows = lst["rows"][:3]
    title = lst.get("title_scoreboard") or lst["title"]
    if len(rows) == 1:  # a one-row list is a single "lead" pill (the free-throw % row in the mockup)
        r = rows[0]
        sub = _row_sub(ctx, lst, r, with_values=False)
        body = (
            f'<a class="st-leader-board__pill" href="#"><span class="st-leader-board__digits">{esc(r["value"])}</span>'
            f'<span class="st-leader-board__who"><span class="st-leader-board__name">{esc(r["name"])}</span>'
            f'<span class="st-leader-board__sub">{esc(sub)}</span></span></a>'
        )
    else:
        items = []
        for i, r in enumerate(rows):
            sub = _row_sub(ctx, lst, r, with_values=False)
            first = " st-leader-board__row--first" if i == 0 else ""
            items.append(
                f'<li><a class="st-leader-board__row{first}" href="#">'
                f'<span class="st-leader-board__value"><span class="st-visually-hidden">{r["rank"]}. </span>{esc(r["value"])}</span>'
                f'<span class="st-leader-board__who"><span class="st-leader-board__name">{esc(r["name"])}</span>'
                f'<span class="st-leader-board__sub">{esc(sub)}</span></span></a></li>'
            )
        body = f'<ol class="st-leader-board__rows">{"".join(items)}</ol>'
    return f'<div class="st-leader-board"><h3 class="st-leader-board__title">{esc(title)}</h3>{body}</div>'


def render_leader_list(ctx: Ctx) -> str:
    out = []
    for lst in _lists(ctx):
        if is_scoreboard(ctx):
            out.append(_leader_board(ctx, lst))
        elif ctx.layout == "hockey" and lst["columns"]:
            out.append(_hockey_table(ctx, lst))
        else:
            out.append(_leader_rows(ctx, lst))
    if is_scoreboard(ctx):
        out.append(
            f'<a class="st-button st-button--quiet st-leader-more" href="#">{esc(ctx.league["layout_labels"]["scoreboard"]["all_stats"])}</a>'
        )
    return pad(f'<div class="st-leader-lists">{"".join(out)}</div>')


# --------------------------------------------------------------------------- game rows

DIAMOND_SVG = (
    '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">'
    '<path d="M7 1L13 7L7 13L1 7Z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'
)


def surface_kind(ctx: Ctx) -> str:
    """How this layout writes the sheet / pad / diamond: tile label icon tag sub none."""
    if not ctx.league["surface_word"]:
        return "none"
    if ctx.layout == "scoreboard":
        return "tag"
    if ctx.layout == "curling":
        return "tile"
    if ctx.layout == "slopitch":
        return "icon"
    if ctx.layout == "hockey" or (ctx.layout == "classic" and ctx.sport == "hockey"):
        return "sub"
    return "label"


def _strip_pm(ctx: Ctx) -> bool:
    nd = ctx.league["next_day"]
    return bool((ctx.layout == "classic" and nd.get("foot_classic")) or (ctx.layout == "scoreboard" and nd.get("foot_scoreboard")))


def game_row(ctx: Ctx, row: dict, tag: str = "div", show_time: bool = True) -> str:
    kind = surface_kind(ctx)
    word = ctx.league["surface_word"]
    sid = row["surface"]
    time = row["time"].replace(" PM", "") if _strip_pm(ctx) else row["time"]
    surface = ""
    sub = ""
    if kind != "none" and sid:
        full = f"{word} {sid}"
        if kind == "tile":
            surface = f'<span class="st-game-row__surface st-game-row__surface--tile"><span class="st-visually-hidden">{esc(word)} </span>{esc(sid)}</span>'
        elif kind == "label":
            surface = f'<span class="st-game-row__surface st-game-row__surface--label">{esc(full)}</span>'
        elif kind == "icon":
            surface = f'<span class="st-game-row__surface st-game-row__surface--icon">{DIAMOND_SVG}<span>{esc(full)}</span></span>'
        elif kind == "tag":
            surface = (f'<span class="st-game-row__surface st-game-row__surface--tag"><span class="st-visually-hidden">{esc(full)}</span>'
                       f'<span aria-hidden="true">{esc(word[0] + sid)}</span></span>')
        elif kind == "sub":
            sub = f'<span class="st-game-row__sub">{esc(full)}</span>'
    time_html = f'<span class="st-game-row__time">{esc(time)}{sub}</span>' if show_time else ""
    mods = ""
    if not surface:
        mods += " st-game-row--no-surface"
    if not show_time:
        mods += " st-game-row--no-time"
    teams = (
        f'<span class="st-game-row__teams">{esc(tname(ctx, row["home"]))} '
        f'<span class="st-game-row__vs">vs</span> {esc(tname(ctx, row["away"]))}</span>'
    )
    href = ' href="#"' if tag == "a" else ""
    return f'<{tag} class="st-game-row{mods}"{href}>{surface}{teams}{time_html}</{tag}>'


def _flat_rows(ctx: Ctx) -> list[dict]:
    return [r for g in ctx.league["next_day"]["groups"] for r in g["rows"]]


def render_game_row(ctx: Ctx) -> str:
    nd = ctx.league["next_day"]
    grouped = ctx.layout == "curling"  # curling's panel prints the time once per group, not on each row
    panel_rows = []
    for g in nd["groups"]:
        if grouped and g["time_label"]:
            panel_rows.append(f'<p class="st-next-game__group-label">{esc(g["time_label"])}</p>')
        panel_rows.append(
            '<div class="st-next-game__rows">'
            + "".join(game_row(ctx, r, show_time=not grouped) for r in g["rows"]) + "</div>"
        )
    panel = f'<div class="st-next-game st-next-game--demo"><div class="st-next-game__body">{"".join(panel_rows)}</div></div>'
    listing = (
        '<div class="st-game-rows st-game-rows--list">'
        + "".join(game_row(ctx, r, tag="a") for r in _flat_rows(ctx)) + "</div>"
    )
    return pad(
        '<p class="st-label st-specimen-label">On a panel</p>' + panel
        + '<p class="st-label st-specimen-label">On the page (schedule list)</p>' + listing
    )


# --------------------------------------------------------------------------- next-game panel

HOUSE_SVG = (
    '<svg class="st-next-game__emblem st-next-game__emblem--house" width="44" height="44" viewBox="0 0 44 44" '
    'aria-hidden="true" focusable="false"><circle class="r1" cx="22" cy="22" r="21"/><circle class="r2" cx="22" cy="22" r="15"/>'
    '<circle class="r3" cx="22" cy="22" r="9.5"/><circle class="r4" cx="22" cy="22" r="4"/></svg>'
)
FACEOFF_SVG = (
    '<svg class="st-next-game__emblem st-next-game__emblem--faceoff" width="150" height="150" viewBox="0 0 150 150" '
    'aria-hidden="true" focusable="false"><circle class="ring" cx="75" cy="75" r="60"/><circle class="dot" cx="75" cy="75" r="7"/>'
    '<path class="ticks" d="M40 63h16M40 87h16M94 63h16M94 87h16M60 50v8M60 92v8M90 50v8M90 92v8"/></svg>'
)


def render_next_game(ctx: Ctx) -> str:
    nd = ctx.league["next_day"]
    sb = is_scoreboard(ctx)
    house = ctx.layout == "curling"
    faceoff = ctx.layout == "hockey"
    grouped = ctx.layout == "curling"
    label = lab(ctx, "next") if sb else nd["eyebrow"]
    date = nd["label_short"] if sb else nd["label"]
    where = " · ".join(x for x in (nd["where"], nd.get("week_label"), nd.get("where_note")) if x)

    body = [f'<p class="st-next-game__where">{esc(where)}</p>']
    for g in nd["groups"]:
        if grouped and g["time_label"]:
            body.append(f'<p class="st-next-game__group-label">{esc(g["time_label"])}</p>')
        body.append(
            '<div class="st-next-game__rows">'
            + "".join(game_row(ctx, r, show_time=not grouped) for r in g["rows"]) + "</div>"
        )
    if sb:
        foot = nd.get("foot_scoreboard") or (f'Bye: <b>{esc(tname(ctx, nd["bye"]))}</b>' if nd["bye"] else esc(nd["foot"]))
        link = ""
    else:
        foot = esc(nd.get("foot_classic") if ctx.layout == "classic" and nd.get("foot_classic") else nd["foot"])
        link = f'<a href="#">{esc(nd["foot_link"])}</a>' if nd.get("foot_link") else ""
    body.append(f'<div class="st-next-game__foot"><span>{foot}</span>{link}</div>')

    mod = " st-next-game--house" if house else " st-next-game--faceoff" if faceoff else ""
    emblem = HOUSE_SVG if house else FACEOFF_SVG if faceoff else ""
    return pad(
        f'<section class="st-next-game{mod}" aria-labelledby="ng-{ctx.layout}-{ctx.theme}-{ctx.sport}">{emblem}'
        f'<div class="st-next-game__head"><h2 class="st-next-game__label" id="ng-{ctx.layout}-{ctx.theme}-{ctx.sport}">{esc(label)}</h2>'
        f'<p class="st-next-game__date">{esc(date)}</p></div>'
        f'<div class="st-next-game__body">{"".join(body)}</div></section>'
    )


# --------------------------------------------------------------------------- team card


def render_team_card(ctx: Ctx) -> str:
    st = ctx.league["standings"]
    rows = st["rows"]
    picks = [(1, rows[0]), (2, rows[1]), (len(rows), rows[-1])]
    cards = []
    for rank, row in picks:
        t = team_by_id(ctx.league, row["team"])
        pts = row["values"].get("PTS")
        points = f'<span class="st-team-card__points"> · {pts} pts</span>' if pts is not None else ""
        skip = f'<span class="st-team-card__sub">Skip {esc(t["skip"])}</span>' if ctx.sport == "curling" and t.get("skip") else ""
        cards.append(
            f'<a class="st-team-card st-team--{t["slot"]}" href="#">'
            f'<span class="st-team-card__name">{esc(t["name"])}</span>'
            f'<span class="st-team-card__record">{esc(t["record"])}{points}</span>'
            f'{skip}<span class="st-team-card__rank">No. {rank} in the standings</span></a>'
        )
    return pad(f'<div class="st-list">{"".join(cards)}</div>')


# --------------------------------------------------------------------------- the parts

PARTS = [
    Part(
        "standings", "Standings", "Data", render_standings,
        note="Table with the key (points) column bold, team chip beside the name, sticky first column; "
             "the Scoreboard shows 'The race' instead (bars, full table linked in the note).",
    ),
    Part(
        "standings-table", "Standings table in the Scoreboard", "Data", render_standings_table,
        layouts=("scoreboard",),
        note="The page the race links to: the same table, in the Scoreboard's heavy skin.",
    ),
    Part(
        "leader-tile", "Leader tiles", "Data", render_leader_tile,
        note="Two-up tiles; the coloured top edge (or, in Curling, the number's colour) comes from --hot / --accent. "
             "Hockey's goalies sit under their own label.",
    ),
    Part(
        "leader-list", "Leader list, table and board", "Data", render_leader_list,
        note="Rows with a rank number (Classic: round rank chip); hockey's points are a table with round rank chips; "
             "the Scoreboard shows ranked boards with huge numbers, first row heavier, and a pill for a one-row list.",
    ),
    Part(
        "game-row", "Game row", "Data", render_game_row,
        note="Grid areas surface / teams / time. Shown on a panel (translucent) and as a list on the page.",
    ),
    Part(
        "next-game", "Next-game panel", "Data", render_next_game,
        note="Filled panel (Scoreboard: outlined box with a black title bar). Curling draws are grouped by time "
             "and carry the house rings; hockey carries a face-off circle.",
    ),
    Part(
        "team-card", "Team card", "Data", render_team_card,
        note="Not mocked in round 1: please review. Colour edge from --st-team; name, record and points, rank line.",
    ),
]
