"""Specimens for the Shell group: header, nav, theme button, ticker, footer, page title,
section heading.  Markup follows docs/design.md "Part anatomy > Shell"; class names are
the contract with stage 4's Jekyll includes.  Everything shown comes from sample.py.
"""
from __future__ import annotations

from .model import MOON_SVG, SUN_SVG, Ctx, Part, esc, team_by_id


# ----------------------------------------------------------------- shared bits

def _badge(league: dict, small: bool = False) -> str:
    cls = "st-brand__badge st-brand__badge--sm" if small else "st-brand__badge"
    label = "" if small else f' role="img" aria-label="{esc(league["name"])} badge"'
    hidden = ' aria-hidden="true"' if small else ""
    return f'<span class="{cls}"{label}{hidden}>{esc(league["code"])}</span>'


def _brand_name(league: dict) -> str:
    """Short name; its last word sits in a tint span (Scoreboard colours it)."""
    words = league["short_name"].split(" ")
    if len(words) < 2:
        return esc(league["short_name"])
    return f'{esc(" ".join(words[:-1]))} <span class="st-brand__tint">{esc(words[-1])}</span>'


def _toggle(state: str = "to-dark") -> str:
    """state 'to-dark' = light page, shows the moon; 'to-light' = dark page, shows the sun."""
    if state == "to-dark":
        return ('<button class="st-theme-toggle" type="button" aria-label="Switch to dark theme">'
                f'{MOON_SVG}</button>')
    return ('<button class="st-theme-toggle" type="button" aria-label="Switch to light theme">'
            f'{SUN_SVG}</button>')


def _nav(league: dict, current: str) -> str:
    cur = ' aria-current="page"'
    links = "".join(
        f'<a class="st-nav__link" href="#"{cur if item == current else ""}>{esc(item)}</a>'
        for item in league["nav"]
    )
    return f'<nav class="st-nav" aria-label="Main">{links}</nav>'


def _header(league: dict, current: str = "Home") -> str:
    return (
        '<header class="st-header">'
        '<div class="st-header__top">'
        '<a class="st-brand" href="#">'
        f'{_badge(league)}'
        '<span class="st-brand__text">'
        f'<span class="st-brand__name">{_brand_name(league)}</span>'
        f'<span class="st-brand__meta">{esc(league["tagline"])}</span>'
        '</span></a>'
        f'{_toggle("to-dark")}'
        '</div>'
        f'{_nav(league, current)}'
        '<div class="st-header__scene" aria-hidden="true"></div>'
        '</header>'
    )


# -------------------------------------------------------------------- parts

def render_header(ctx: Ctx) -> str:
    return _header(ctx.league, "Home")


def render_nav(ctx: Ctx) -> str:
    # A header wrapper gives the tabs their ground; the current tab here is Stats.
    return f'<div class="st-header">{_nav(ctx.league, "Stats")}</div>'


def render_toggle(ctx: Ctx) -> str:
    # Both states on a header-coloured strip: the moon on a light page ("to dark"),
    # the sun on a dark page ("to light").
    cap = ('<span style="margin:0 0.75rem 0 0.25rem;font-size:var(--st-fs-meta);'
           'line-height:1.2;color:var(--st-header-muted)">{}</span>')
    return (
        '<div class="st-header"><div class="st-header__top" style="padding-bottom:0.75rem">'
        f'{_toggle("to-dark")}{cap.format("Light page:<br>moon")}'
        f'{_toggle("to-light")}{cap.format("Dark page:<br>sun")}'
        '</div></div>'
    )


def _ticker_items(league: dict) -> str:
    out: list[str] = []
    for res in league["results"]:
        a, b = team_by_id(league, res["home"]), team_by_id(league, res["away"])
        out.append(f'<span class="st-ticker__tag">{esc(res["status"])}</span>')
        out.append(f'<span class="st-ticker__item">{esc(a["code"])} {res["scores"][a["id"]]} · '
                   f'{esc(b["code"])} {res["scores"][b["id"]]}</span>')
        out.append('<span class="st-ticker__sep" aria-hidden="true">|</span>')
    if league.get("bye"):
        bye = team_by_id(league, league["bye"])
        out.append(f'<span class="st-ticker__item st-ticker__item--quiet">{esc(bye["code"])} bye</span>')
    elif out:
        out.pop()  # no trailing separator
    return "".join(out)


def render_ticker(ctx: Ctx) -> str:
    # role="region" + tabindex make the strip reachable and scrollable by keyboard.
    return (f'<div class="st-ticker" role="region" tabindex="0" aria-label="Latest scores">'
            f'{_ticker_items(ctx.league)}</div>')


def render_footer(ctx: Ctx) -> str:
    lg = ctx.league
    links = "".join(f'<a href="#">{esc(t)}</a>' for t in lg["footer_links"])
    where = f'<p class="st-footer__where">{esc(lg["footer_line"])}</p>' if lg["footer_line"] else ""
    return (
        '<footer class="st-footer">'
        '<div class="st-footer__scene" aria-hidden="true"></div>'
        '<div class="st-footer__body">'
        '<div class="st-footer__brand">'
        f'{_badge(lg, small=True)}'
        f'<span class="st-footer__name">{esc(lg["footer_name"])}</span>'
        '</div>'
        f'<nav class="st-footer__nav" aria-label="Footer">{links}</nav>'
        f'{where}'
        f'<p class="st-footer__credit">Made with <a href="#">scorers-table</a></p>'
        '</div></footer>'
    )


def render_page_title(ctx: Ctx) -> str:
    lg = ctx.league
    g = lg["game"]
    h = g["header"]
    eyebrow = f'<p class="st-page-title__eyebrow">{esc(h["eyebrow"])}</p>' if h["eyebrow"] else ""
    sub = esc(h["subline"]) + (f'<br>{esc(h["venue_line"])}' if h["venue_line"] else "")
    return (
        '<div class="st-main" style="padding-block:0 var(--st-space-lg)"><div class="st-page-title">'
        f'<a class="st-back" href="#">{esc(g["back_label"])}</a>'
        f'{eyebrow}'
        f'<h1 class="st-page-title__title">{esc(h["title"])}</h1>'
        f'<p class="st-page-title__sub">{sub}</p>'
        '</div></div>'
    )


def render_section(ctx: Ctx) -> str:
    lg = ctx.league
    labels = {**lg["labels"], **lg.get("layout_labels", {}).get(ctx.layout, {})}
    rh = lg["results_header"]
    # Scoreboard renames sections ("The race"); the date aside is unchanged.
    first_title = labels["results"] if ctx.layout != "scoreboard" else lg["featured"]["label"]
    placeholder = '<div class="st-card" style="padding:var(--st-card-pad-y) var(--st-card-pad-x)"><span class="st-label">Section content</span></div>'
    return (
        '<div class="st-main" style="padding-bottom:var(--st-space-lg)">'
        '<section class="st-section">'
        '<div class="st-section__head">'
        f'<h2 class="st-section__title">{esc(first_title)}</h2>'
        f'<span class="st-section__aside">{esc(rh["meta"])}</span>'
        f'</div>{placeholder}</section>'
        '<section class="st-section">'
        '<div class="st-section__head">'
        f'<h2 class="st-section__title">{esc(labels["standings"])}</h2>'
        f'<a class="st-section__aside" href="#">{esc(labels["full_table"])}</a>'
        f'</div>{placeholder}'
        f'<p class="st-note">{esc(lg["points_note"])}</p></section>'
        '</div>'
    )


PARTS = [
    Part(
        id="header", title="Header", group="Shell", render=render_header,
        note="Brand (monogram badge, name, meta line), theme button and nav tabs; Home is the current tab. "
             "The scene behind it comes from the layout file.",
    ),
    Part(
        id="nav", title="Nav tabs", group="Shell", render=render_nav,
        note="Five tabs; the current one (here Stats) has the underline. Scrolls inside itself if it ever overflows.",
    ),
    Part(
        id="theme-toggle", title="Theme button", group="Shell", render=render_toggle,
        note="44 px round button: the moon (page is light, switches to dark) and the sun (page is dark, switches to light).",
    ),
    Part(
        id="ticker", title="Ticker", group="Shell", render=render_ticker, layouts=("scoreboard",),
        note="Scoreboard only: the latest scores in a dark strip under the header; scrolls inside itself.",
    ),
    Part(
        id="footer", title="Footer", group="Shell", render=render_footer,
        note="Logo badge and name, links (44 px targets), where/when line and the credit.",
    ),
    Part(
        id="page-title", title="Page title block", group="Shell", render=render_page_title,
        note="Top of a game or team page: back link, eyebrow, h1, date and venue line.",
    ),
    Part(
        id="section-heading", title="Section heading", group="Shell", render=render_section,
        note="Title with a date aside, title with a link aside plus a note. Hockey draws three rink lines before the title.",
    ),
]
