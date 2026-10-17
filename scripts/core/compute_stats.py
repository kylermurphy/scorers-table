"""`<season>/players.json` and `<season>/leaders.json`: player totals, rankings and the leaderboards
(docs/stage-4-spec.md 4.1, docs/design.md "Stage 4 includes").

* A line in a game file gives a player one game played (`gp` is the core's, not the sport's). Totals are the
  sums of the sport's counting stats over the regular season; playoff lines are totalled apart (`playoffs`),
  as the Masters site does. Rates (`derive`) are worked out from the summed counts through `call_sport`, so a
  game page and the stats page agree.
* Rates (`derive`) may come back unrounded: `totals` hold them rounded half up to the stat's `places` (what the
  pages show) and boards rank on the exact value, so 20.14 is ahead of 20.06 although both show 20.1.
* A leaderboard is one entry of sport.yml `leaderboards`. Each becomes ONE board with `list: true`; one with
  `tile: true` also draws a leader tile from its first row, and then its list starts at rank 2
  (`first_row_in_tile`). Ranks are competition ranks (1, 2, 2, 4), equal values listed by name, then number
  (`name_order`); a value of 0 or "—" is not a leader,
  except on a board with `zero: true` (a 0 is ranked, "—" never). Board switches from sport.yml: `playoffs: true`
  counts playoff games too, `home: false` keeps the board off the Home page, `player_rank: false` keeps it out
  of a player's "Ranks" line.
* A board's minimum (sport.yml `min`) is the league's number for that setting (`stats.minimums`). With
  `cap_at_team_games` it never asks for more games than the player's team has played, so the early season is not
  empty. Players below it are listed in `unranked`. A minimum the league has not decided shows `[placeholder]`
  in the note (the number used meanwhile is the sport's default).
* `leaders.columns[group]` is `{table, totals, log}`: the columns of the Stats table, of a player's season
  totals and of a game log. sport.yml `stats.columns.<group>` lists them; left out, each is GP, the counting
  stats, then the rates.
* Boards show the first `LEADERS_SHOWN` ranks (ties at the last rank included); the Stats table lists everyone.
"""
from __future__ import annotations

from typing import Any

from scripts.core import fmt
from scripts.core.loader import LoadedGame
from scripts.core.model import STAT_RESERVED, Line, Player
from scripts.core.problems import call_sport
from scripts.core.compute_games import decided_word
from scripts.core.season_ctx import SeasonCtx, dash, game_url, player_url, result_word
from scripts.core.standings import record_of

LEADERS_SHOWN = 10


class _Played:
    """One player's line in one game."""
    __slots__ = ("game", "line")

    def __init__(self, game: LoadedGame, line: Line) -> None:
        self.game, self.line = game, line


def build_stats(ctx: SeasonCtx) -> tuple[dict, dict]:
    """(players.json, leaders.json) for one season."""
    played = _collect(ctx)
    groups = _groups(ctx)
    totals = {(pid, g, kind): _stat_block(ctx, g, rows) for (pid, g, kind), rows in played.items()}
    boards, ranks = _boards(ctx, totals, played)
    players = {pid: _player(ctx, p, groups, played, totals, ranks) for pid, p in ctx.players.items()}
    leaders = {"boards": boards, "table": _table(ctx, groups, totals, boards), "columns": {
        g: _columns(ctx, g, _observed(totals, g)) for g in groups}}
    return players, leaders


# ------------------------------------------------------------------ collecting lines

def _groups(ctx: SeasonCtx) -> list[str]:
    """The stat groups of the sport ('player', or 'skater' and 'goalie'), in sport.yml order."""
    return [g for g in ctx.spec["stats"] if g not in STAT_RESERVED]


def _collect(ctx: SeasonCtx) -> dict[tuple[str, str, str], list[_Played]]:
    """{(player id, group, 'regular' | 'playoff'): lines in date order}."""
    out: dict[tuple[str, str, str], list[_Played]] = {}
    for game in ctx.finished():
        if game.reading is None:
            continue
        for line in game.reading.lines:
            out.setdefault((line.player, line.group, game.row.type), []).append(_Played(game, line))
    return out


def _defs(ctx: SeasonCtx, group: str) -> list[dict]:
    """Every stat of a group: gp, the counting stats, then the rates."""
    stats = ctx.spec["stats"]
    return ([{"key": "gp", "label": "GP", "title": "Games played"}] + list(stats[group])
            + [dict(d, derived=True) for d in stats["derived"]])


def _stat_block(ctx: SeasonCtx, group: str, rows: list[_Played]) -> dict:
    """{'totals': values, 'display': strings, 'exact': unrounded rates} for a set of lines (one game or a season).
    `derive` may return a rate unrounded: `totals` and `display` hold it rounded half up to the stat's `places`,
    `exact` keeps what `derive` returned (boards rank on it) and never reaches the JSON files."""
    counts = {s["key"]: sum(r.line.counts.get(s["key"], 0) for r in rows) for s in ctx.spec["stats"][group]}
    counts["gp"] = len(rows)
    rates = call_sport("derive", ctx.league.sport_def.rules.derive, dict(counts), group)
    totals: dict[str, Any] = {"gp": counts["gp"], **{k: v for k, v in counts.items() if k != "gp"}}
    display = {key: str(value) for key, value in totals.items()}
    exact: dict[str, Any] = {}
    for d in ctx.spec["stats"]["derived"]:
        rate = rates.get(d["key"])
        places = d.get("places", 1)
        exact[d["key"]] = rate
        totals[d["key"]] = rate if rate is None or isinstance(rate, int) else fmt.round_half_up(rate, places)
        display[d["key"]] = fmt.decimal(rate, places)
    return {"totals": totals, "display": display, "exact": exact}


def _observed(totals: dict, group: str) -> set[str]:
    return {k for (_, g, kind), block in totals.items() if g == group and kind == "regular"
            for k, v in block["totals"].items() if v is not None}


# ------------------------------------------------------------------ leaderboards

def _boards(ctx: SeasonCtx, totals: dict, played: dict) -> tuple[list[dict], dict[str, dict[str, int]]]:
    boards, ranks = [], {}
    tiles = 0
    for spec in ctx.spec["leaderboards"]:
        edge = spec.get("edge") or ("hot" if tiles == 0 else "accent")
        tiles += 1 if spec.get("tile") else 0
        if spec["of"] == "team":
            board = _team_board(ctx, spec, edge)
        else:
            board = _player_board(ctx, spec, edge, totals, played, ranks)
        boards.append(board)
    return boards, ranks


def _board(ctx: SeasonCtx, spec: dict, edge: str, minimum: dict, unit: str) -> dict:
    group = spec.get("group", "player")
    return {"id": spec["id"], "label": spec["label"], "of": spec["of"], "group": group,
            "group_label": group.title() if len(_groups(ctx)) > 1 else None, "stat": spec["stat"],
            "tile": bool(spec.get("tile")), "list": True, "edge": edge, "home": spec.get("home", True),
            "player_rank": spec.get("player_rank", True), "min": minimum, "unranked": [],
            "columns": None, "title": spec["label"], "title_board": None, "unit": unit,
            "first_row_in_tile": bool(spec.get("tile")), "rows": []}


def _stat_label(ctx: SeasonCtx, group: str, key: str) -> str:
    return next((d["label"] for d in _defs(ctx, group) if d["key"] == key), key)


def _minimum(ctx: SeasonCtx, spec: dict) -> dict:
    """{'value', 'placeholder', 'note'} for a board's minimum; all empty when the board has none."""
    rule = spec.get("min")
    if not rule:
        return {"value": None, "placeholder": False, "note": None}
    setting = rule["setting"]
    value = ctx.settings.minimums[setting]
    placeholder = ctx.is_placeholder(f"stats.minimums.{setting}")
    sport_min = ctx.spec["minimums"][setting]
    template = sport_min.get("note")
    shown = fmt.PLACEHOLDER if placeholder else value
    if template and (placeholder or value > 0):
        note = template.format(value=shown)
    elif placeholder:
        note = f"{sport_min.get('label') or fmt.humanize(setting)}: {fmt.PLACEHOLDER}."
    else:
        note = None
    return {"value": value, "placeholder": placeholder, "note": note}


def _entries(ctx: SeasonCtx, spec: dict, totals: dict, played: dict) -> list[tuple[str, dict]]:
    """[(player id, stat block)] one per player of the board's group: the regular season, or with
    `playoffs: true` the regular season and the playoffs together."""
    group = spec.get("group", "player")
    if spec.get("playoffs"):
        pids = dict.fromkeys(pid for (pid, g, _) in played if g == group)
        return [(pid, _stat_block(ctx, group, played.get((pid, group, "regular"), []) + played.get((pid, group, "playoff"), [])))
                for pid in pids]
    return [(pid, block) for (pid, g, kind), block in totals.items() if g == group and kind == "regular"]


def _player_board(ctx: SeasonCtx, spec: dict, edge: str, totals: dict, played: dict, ranks: dict) -> dict:
    group, stat = spec.get("group", "player"), spec["stat"]
    minimum = _minimum(ctx, spec)
    board = _board(ctx, spec, edge, minimum, _stat_label(ctx, group, stat))
    rule = spec.get("min")
    zero = bool(spec.get("zero"))
    eligible, unranked = [], []
    for pid, block in _entries(ctx, spec, totals, played):
        value = block["exact"][stat] if stat in block["exact"] else block["totals"].get(stat)
        if value is None or (value <= 0 and not zero):
            continue
        if rule and block["totals"][rule["stat"]] < _needed(ctx, rule, minimum["value"], ctx.players[pid]):
            unranked.append(pid)
        else:
            eligible.append((pid, block, value))
    eligible.sort(key=lambda x: (-x[2], *name_order(ctx.players[x[0]])))
    rank = 0
    for i, (pid, block, value) in enumerate(eligible):
        rank = rank if i and value == eligible[i - 1][2] else i + 1
        if spec.get("player_rank", True):          # the first board on a stat gives the rank
            ranks.setdefault(pid, {}).setdefault(group, {}).setdefault(stat, rank)
        if rank <= LEADERS_SHOWN:
            player = ctx.players[pid]
            board["rows"].append({
                "rank": rank, "player": pid, "team": player.team, "label": player.label,
                "value": block["totals"][stat], "display": block["display"][stat],
                "detail": _detail(spec, block["display"]), "cells": None})
    board["unranked"] = sorted(unranked)
    return board


def name_order(player: Player) -> tuple:
    """Players with equal values are listed by name ("First L.", without the number), then by number as a number
    (#5 before #38; none last), then by id, so the order is stable."""
    number = player.number
    return (player.name.casefold(), number is None, int(number) if number is not None else 0, number or "", player.id)


def _needed(ctx: SeasonCtx, rule: dict, minimum: int, player: Player) -> int:
    """The minimum for this player: the league's number, but never more than their team's games so far."""
    if rule.get("cap_at_team_games") and player.team:
        return min(minimum, len(ctx.regular_games(player.team)))
    return minimum


def _detail(spec: dict, display: dict) -> str | None:
    return spec["detail"].format(**display) if spec.get("detail") else None


def _team_board(ctx: SeasonCtx, spec: dict, edge: str) -> dict:
    """A board of teams, ranked on one of the sport's team stats (summed over the regular season)."""
    stat = spec["stat"]
    board = _board(ctx, spec, edge, _minimum(ctx, spec), next((s["label"] for s in ctx.spec["stats"]["team"]
                                                               if s["key"] == stat), stat))
    keys = ctx.team_stat_keys()
    entries = []
    for team in ctx.teams.values():
        rec = record_of(ctx.regular_games(team.id), keys)
        value = rec.stats.get(stat, 0)
        if value > 0:
            entries.append((team, rec, value))
    entries.sort(key=lambda x: (-x[2], x[0].name.casefold(), x[0].id))
    for i, (team, rec, value) in enumerate(entries):
        rank = board["rows"][-1]["rank"] if i and value == entries[i - 1][2] else i + 1
        if rank > LEADERS_SHOWN:
            break
        board["rows"].append({"rank": rank, "player": None, "team": team.id, "label": team.name, "value": value,
                              "display": str(value), "detail": _detail(spec, _team_display(rec, stat)), "cells": None})
    return board


def _team_display(rec, stat: str) -> dict[str, str]:
    shown = {c: str(getattr(rec, c)) for c in ("gp", "w", "l", "t", "otw", "otl", "pts", "pf", "pa", "pw")}
    shown.update({"diff": fmt.signed(rec.diff), "pct": fmt.win_pct(rec.w, rec.l, rec.t), "gb": fmt.DASH})
    shown.update({k: str(v) for k, v in rec.stats.items()})
    return shown


# ------------------------------------------------------------------ the Stats table

def _columns(ctx: SeasonCtx, group: str, seen: set[str]) -> dict[str, list[dict]]:
    """{table, totals, log}: the columns of the Stats table, of a player's season totals and of a game log.
    sport.yml `stats.columns.<group>` lists the keys of each in order; a list left out is GP, the counting stats
    and the rates the sport worked out. A rate nobody has a value for is left out of every list (once anyone
    has played). The key column is the first leaderboard's stat for the group when the list has it, else the
    first column after GP."""
    defs = {d["key"]: d for d in _defs(ctx, group) if not d.get("derived") or d["key"] in seen or not seen}
    chosen = ctx.spec["stats"].get("columns", {}).get(group, {})
    first = next((b["stat"] for b in ctx.spec["leaderboards"]
                  if b["of"] == "player" and b.get("group", "player") == group), None)
    out = {}
    for name in ("table", "totals", "log"):
        keys = [k for k in chosen.get(name, list(_defs_keys(ctx, group))) if k in defs]
        key = first if first in keys else next((k for k in keys if k != "gp"), None)
        out[name] = [{"key": k, "label": defs[k]["label"], "title": defs[k]["title"], "key_col": k == key} for k in keys]
    return out


def _defs_keys(ctx: SeasonCtx, group: str) -> list[str]:
    return [d["key"] for d in _defs(ctx, group)]


def _table(ctx: SeasonCtx, groups: list[str], totals: dict, boards: list[dict]) -> dict | None:
    """Everyone who played, best first on the key column (ties by name): ids only, the page reads players.json."""
    if not groups:
        return None
    group = groups[0]
    columns = _columns(ctx, group, _observed(totals, group))["table"]
    key = next((c["key"] for c in columns if c["key_col"]), None)
    ids = [pid for (pid, g, kind) in totals if g == group and kind == "regular"]

    def order(pid: str):                       # a rate sorts on its exact value, as the boards rank it
        block = totals[(pid, group, "regular")]
        value = (block["exact"][key] if key in block["exact"] else block["totals"].get(key)) if key else None
        return (value is None, -(value or 0), *name_order(ctx.players[pid]))

    return {"group": group, "columns": columns, "rows": sorted(ids, key=order)}


# ------------------------------------------------------------------ one player

def _player(ctx: SeasonCtx, player: Player, groups: list[str], played: dict, totals: dict, ranks: dict) -> dict:
    mine = {g: totals[(player.id, g, "regular")] for g in groups if (player.id, g, "regular") in totals}
    playoffs = {g: totals[(player.id, g, "playoff")] for g in groups if (player.id, g, "playoff") in totals}
    team = ctx.teams.get(player.team) if player.team else None
    return {
        "id": player.id, "name": player.name, "label": player.label, "number": player.number, "team": player.team,
        "team_name": team.name if team else None, "sub": player.sub, "position": player.position,
        "url": player_url(player.id) if ctx.active else None,
        "groups": {g: {"totals": b["totals"], "display": b["display"], "ranks": ranks.get(player.id, {}).get(g, {})}
                   for g, b in mine.items()},
        "log": _log(ctx, player, groups, played),
        "playoffs": {g: {"totals": b["totals"], "display": b["display"]} for g, b in playoffs.items()},
    }


def _log(ctx: SeasonCtx, player: Player, groups: list[str], played: dict) -> list[dict]:
    """The player's games in date order (regular season and playoffs): the opponent, the result and the line."""
    entries = []
    for g in groups:
        for kind in ("regular", "playoff"):
            for p in played.get((player.id, g, kind), []):
                entries.append((p.game.row.date, p.game.row.time, p.game.id, _log_entry(ctx, g, kind, p)))
    return [entry for *_, entry in sorted(entries, key=lambda e: e[:3])]


def _log_entry(ctx: SeasonCtx, group: str, kind: str, p: _Played) -> dict:
    game = p.game
    mine = ctx.results[game.id][getattr(game, p.line.side)]
    other = ctx.results[game.id][mine.opponent]
    # "Win", or "Win (OT)" / "Loss (EE)" after extra play: the sport's `words.extra.short`, as the final panel says it.
    extra = decided_word(ctx, game.reading.score.decided_in) if game.reading and mine.result in ("ot_win", "ot_loss") else None
    return {"game": game.id, "url": game_url(game.id), "type": kind, "group": group,
            "date_short": fmt.date_short(game.row.date), "opponent": ctx.team_name(mine.opponent),
            "result": mine.result, "result_label": result_word(mine.result) + (f" ({extra})" if extra else ""),
            "score": dash(f"{mine.pf}-{other.pf}"),
            "display": _stat_block(ctx, group, [p])["display"]}
