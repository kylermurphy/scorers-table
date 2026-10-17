"""`<season>/games.json`: one entry per finished game, the sport's `present()` output turned into the shapes
the includes read (docs/stage-4-spec.md 4.1, docs/design.md "Stage 4 includes").

Only games with a score sheet or a forfeit appear (a scheduled game has no page). The core adds what a sport
should not have to write: the sides (names, codes, colours, results, records), the final panel's status and
sub line, the card's meta, the line score's caption and defaults, and the box score's number column.

Choices: the standings points of a playoff game are `None` (playoff games never count); a forfeit has no
line score (its card says who forfeited); `decided_in` is "regulation" for a forfeit; a side's record is the
record through that game (for a playoff game, the final regular-season record).
"""
from __future__ import annotations

import copy

from scripts.core import fmt
from scripts.core.loader import LoadedGame
from scripts.core.problems import call_sport
from scripts.core.season_ctx import SeasonCtx, game_url, league_labels, record_text, result_word

SIDES = ("home", "away")
OVERTIME_WORD = {"overtime": "OT", "shootout": "SO"}


def build_games(ctx: SeasonCtx) -> dict[str, dict]:
    """{game id: game}, in date, time, game id order."""
    labels = {(d, kind): ctx.day_label(rows) for d, kind, rows in ctx.days()}
    return {g.id: game_json(ctx, g, labels[(g.row.date, g.row.type)]) for g in ctx.finished()}


def game_json(ctx: SeasonCtx, game: LoadedGame, day_label: str) -> dict:
    row = game.row
    counted = ctx.results[game.id]
    present = _present(ctx, game)
    final = _final(ctx, game, counted)
    card = _card(ctx, game, present)
    photo = _photo_url(ctx, game)
    return {
        "id": game.id, "url": game_url(game.id), "type": row.type, "round": row.round, "day_label": day_label,
        "date_short": fmt.date_short(row.date), "date_long": fmt.date_long(row.date),
        "time_display": ctx.time_display(row), "venue": ctx.venue_of(row), "surface_label": ctx.surface_label(row),
        "home": _side(ctx, game, "home", counted), "away": _side(ctx, game, "away", counted),
        "tie": counted[game.home].result == "tie", "forfeit": game.forfeit,
        "decided_in": game.reading.score.decided_in if game.reading else "regulation",
        "status": final["status"], "final": final, "summary": final["sub"], "notes": list(game.notes),
        "checked_by": game.checked_by or None, "scorekeeper": game.scorekeeper,
        "photo_url": photo,
        "standings_points": None if row.type == "playoff" else {
            "home": counted[game.home].points, "away": counted[game.away].points},
        "line_score": _line_score(ctx, present), "card": card, "tiles": present.get("tiles") if present else None,
        "blocks": [_block(ctx, b) for b in (present or {}).get("blocks", [])],
    }


def _present(ctx: SeasonCtx, game: LoadedGame) -> dict | None:
    """The sport's display blocks; a forfeit has no sheet to present."""
    if game.reading is None:
        return None
    return call_sport("present", ctx.league.sport_def.rules.present, game.reading, game.context)


def _photo_url(ctx: SeasonCtx, game: LoadedGame) -> str | None:
    if not ctx.league.photos or not game.photo:
        return None
    return f"/sheets/{game.id}{game.photo[game.photo.rfind('.'):]}"


# ------------------------------------------------------------------ sides and the final panel

def _side(ctx: SeasonCtx, game: LoadedGame, side: str, counted: dict) -> dict:
    team = ctx.teams[getattr(game, side)]
    mine = counted[team.id]
    record = record_text(ctx.record_after(game.id, team.id))
    line = f"{result_word(mine.result)} · now {record}" if game.row.type == "regular" else result_word(mine.result)
    return {"team": team.id, "name": team.name, "code": team.code, "slot": team.slot, "colour": team.colour,
            "score": mine.pf, "result": mine.result, "record": record, "record_line": line, "badge": ""}


def _final(ctx: SeasonCtx, game: LoadedGame, counted: dict) -> dict:
    """The final panel's status ("Final", "Final · OT", "Forfeit") and the sub line ("Otters by 3")."""
    home, away = counted[game.home], counted[game.away]
    label = league_labels(ctx.league)["final"]
    if game.forfeit:
        # `note` is set only while the forfeit score is a default the league has not confirmed ([placeholder]).
        return {"status": "Forfeit", "sub": f"{ctx.team_name(game.forfeit)} forfeited", "note": ctx.forfeit_default_note()}
    decided = game.reading.score.decided_in if game.reading else "regulation"
    status = label + (f" · {OVERTIME_WORD[decided]}" if decided in OVERTIME_WORD else "")
    if home.result == "tie":
        return {"status": status, "sub": f"Tied {home.pf}–{away.pf}", "note": None}
    winner, loser = (home, away) if home.pf > away.pf else (away, home)
    return {"status": status, "sub": f"{ctx.team_name(winner.team)} by {winner.pf - loser.pf}", "note": None}


def _card(ctx: SeasonCtx, game: LoadedGame, present: dict | None) -> dict:
    """What a result card prints: the note (its bold part), the link, and the meta parts (surface, time)."""
    meta = [m for m in (ctx.surface_label(game.row), ctx.time_display(game.row)) if m]
    if present is None:
        who = ctx.team_name(game.forfeit or "")
        unconfirmed = f" · score {fmt.PLACEHOLDER}" if ctx.is_placeholder("standings.forfeit") else ""
        return {"note": f"{who} forfeited{unconfirmed}", "strong": who, "link_label": "Details", "meta": meta, "note_long": None}
    card = present.get("card") or {}
    return {"note": card.get("note"), "strong": card.get("strong"), "link_label": card.get("link_label") or "Box score",
            "meta": meta, "note_long": card.get("note_long")}


# ------------------------------------------------------------------ line score and blocks

def _line_score(ctx: SeasonCtx, present: dict | None) -> dict | None:
    """The sport's line score with every field the include reads filled in (null / empty when not used)."""
    if present is None or not present.get("line_score"):
        return None
    ls = copy.deepcopy(present["line_score"])
    one = ctx.spec["words"]["period"]["one"].lower()
    ls.setdefault("caption", f"Score by {one}")
    for key in ("extra_label", "title", "meta", "note", "note_strong", "split", "won_word", "mark_word"):
        ls.setdefault(key, None)
    ls.setdefault("legend", [])
    ls.setdefault("legend_stack", False)
    ls.setdefault("void_word", "not played")
    ls.setdefault("blank_word", "blank")
    ls.setdefault("hammer_word", "Hammer")
    for side in SIDES:
        ls["rows"][side].setdefault("extra", None)
        ls["rows"][side].setdefault("hammer_first", False)
    return ls


def _block(ctx: SeasonCtx, block: dict) -> dict:
    """A present() block. A stat table gets its number column (the player's jersey number) and default labels."""
    block = copy.deepcopy(block)
    if block["type"] != "stat_table":
        return block
    block.setdefault("title", None)
    block.setdefault("note", None)
    block.setdefault("totals", None)
    block.setdefault("number_label", "#")
    block.setdefault("player_label", "Player")
    for row in block["rows"]:
        player = ctx.players.get(row["player"])
        row.setdefault("num", (player.number or "") if player else "")
    return block
