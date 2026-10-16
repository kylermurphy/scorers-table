"""Compute: the loaded data -> every file the site reads (docs/stage-4-spec.md section 4, shapes in 4.1).

    compute(league, data, data_dir=..., site_url=..., preview=...) -> (BuildOutput, problems)

Pure: nothing is written and no clock is read (`data.today` and each season's `today` come from the loader).
`BuildOutput` holds, ready for `writer.py`: the JSON files (path under `_data/computed/` -> value), the front
matter of the stub pages, the calendar files and the score-sheet photos to copy.

Top level: league.json, active.json, seasons.json, archive.json, calendars.json. Per shown season (the active
one and the archive's): teams.json, standings.json, schedule.json, results.json, games.json, players.json,
leaders.json. This module owns league, active, seasons, archive, calendars, teams, standings, schedule and
results; games come from `compute_games`, players and leaders from `compute_stats`.

Choices (also listed in the build report):
* The next game day is the first day on or after today with a game that is not cancelled and has no result
  yet (a day whose sheets are all in is over); the latest is the last day with a result. `latest` / `next` are
  the day's `n`, its position in `days` counting from 1.
* "Today" is the season's (the sample season's `as_of`, else the real date), so a sample always looks mid-season.
* `all_times_pm` is true when times are shown 12-hour and every game is in the afternoon or evening; the
  includes then drop " PM" and each day's foot starts "All times PM."
* Past seasons have no team or player pages (ids repeat across seasons), so their `url`s are `null`.
* The stub pages: games for every shown season, players and teams for the active season, archive pages for the
  archive's seasons.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.core import fmt
from scripts.core.calendars import LEAGUE_FILE, CalGame, build_calendars, links
from scripts.core.compute_games import build_games
from scripts.core.compute_stats import build_stats
from scripts.core.loader import LoadedData, ScheduleRow
from scripts.core.model import League, Problem
from scripts.core.problems import has_errors
from scripts.core.season_ctx import (
    SeasonCtx, archive_url, build_ctx, dash, final_score, game_url, league_labels, record_text, team_url,
)
from scripts.core.standings import record_of

NAV = [("Home", "home", "/"), ("Schedule", "schedule", "/schedule/"), ("Stats", "stats", "/stats/"),
       ("Teams", "teams", "/teams/"), ("Archive", "archive", "/archive/")]
ARCHIVE_TOP = 3                      # standings_top lists this many team names

COLUMN_WORDS = {                       # key -> (label, title)
    "gp": ("GP", "Games played"), "w": ("W", "Wins"), "l": ("L", "Losses"), "t": ("T", "Ties"),
    "otw": ("OTW", "Overtime wins"), "otl": ("OTL", "Overtime losses"), "pts": ("PTS", "Points"),
    "pct": ("PCT", "Winning percentage"), "diff": ("DIFF", "Score difference"),
    "gb": ("GB", "Games behind the leader"),
}


@dataclass
class BuildOutput:
    """What a build writes, before it is written."""
    data: dict[str, Any] = field(default_factory=dict)             # "2026-27/teams.json" -> value
    pages: dict[str, dict[str, dict]] = field(                     # "_games" -> {"<id>.md": front matter}
        default_factory=lambda: {"_games": {}, "_players": {}, "_teams": {}, "_archive": {}})
    calendars: dict[str, str] = field(default_factory=dict)        # "league.ics" -> text
    sheets: list[tuple[Path, str]] = field(default_factory=list)   # (photo in data/, file name under sheets/)
    active: str = ""
    seasons: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ the entry point

def compute(league: League, data: LoadedData, *, data_dir: Path, site_url: str = "", preview: bool = False
            ) -> tuple[BuildOutput, list[Problem]]:
    """Work out every season's standings first (their problems stop the build), then every file."""
    ctxs = {sid: build_ctx(league, loaded, active=(sid == data.active)) for sid, loaded in data.loaded.items()}
    problems = [p for c in ctxs.values() for p in c.problems]
    out = BuildOutput(active=data.active or "", seasons=list(data.shown))
    if has_errors(problems) or data.active is None:
        return out, problems
    active = ctxs[data.active]
    calendars = _calendars(league, data, ctxs, site_url)
    out.data["league.json"] = league_json(league, active)
    out.data["active.json"] = _active_json(league, data, active, preview)
    out.data["seasons.json"] = [_season_entry(ctxs[sid], sid == data.active) for sid in data.shown]
    out.data["archive.json"] = [_archive_entry(ctxs[sid]) for sid in data.shown if sid != data.active]
    out.data["calendars.json"] = calendars["json"]
    out.calendars = calendars["files"]
    for sid in data.shown:
        _season_files(out, ctxs[sid], calendars["team_files"] if ctxs[sid].loaded.season.current else set())
        _season_pages(out, ctxs[sid])
        if league.photos:
            out.sheets += [(data_dir / sid / g.photo, f"{g.id}{Path(g.photo).suffix}")
                           for g in ctxs[sid].finished() if g.photo]
    return out, problems


# ------------------------------------------------------------------ league, active, seasons, archive

def league_json(league: League, active: SeasonCtx) -> dict:
    spec = league.sport_def.spec
    words = {k: spec["words"][k] for k in ("surface", "period", "day", "points_for", "points_against")}
    footer_line = league.footer_line or active.loaded.season.venue or ""
    footer_links = [{"label": "Teams", "url": "/teams/"}, {"label": "Past seasons", "url": "/archive/"},
                    {"label": "League rules", "url": "/rules/"}]
    if league.contact_href:
        footer_links.append({"label": "Contact", "url": league.contact_href})
    return {
        "name": league.name, "short_name": league.short_name, "code": league.code, "sport": league.sport,
        "sport_name": spec["name"], "layout": league.layout, "colour": league.colour,
        "colour_dark": league.colour_dark, "logo": league.logo, "tagline": f"{league.tagline} · {active.label}",
        "footer_line": footer_line, "footer_name": league.name, "contact_href": league.contact_href,
        "search_engines": league.search_engines, "lang": league.lang,
        "nav": [{"label": label, "url": url, "key": key} for label, key, url in NAV],
        "footer_links": footer_links, "labels": league_labels(league), "words": words,
        "display": {**spec["display"], "card_head": ""},
        "placeholders": [{"setting": p.setting, "text": p.text} for p in league.placeholders],
    }


def _active_json(league: League, data: LoadedData, active: SeasonCtx, preview: bool) -> dict:
    return {"season": active.sid, "sample_mode": active.loaded.season.sample,
            "archive": [sid for sid in data.shown if sid != data.active], "today": active.today.isoformat(),
            "preview": preview}


def _season_entry(ctx: SeasonCtx, is_active: bool) -> dict:
    season = ctx.loaded.season
    return {"id": season.id, "label": season.label, "sample": season.sample, "current": season.current,
            "active": is_active, "venue": season.venue or ""}


def _archive_entry(ctx: SeasonCtx) -> dict:
    top = [ctx.team_name(r["team"]) for r in ctx.standing.rows[:ARCHIVE_TOP]]
    finished = ctx.finished()
    return {"season": ctx.sid, "label": ctx.label, "sample": ctx.loaded.season.sample, "url": archive_url(ctx.sid),
            "teams": len(ctx.teams), "games": len(finished), "standings_top": top,
            "playoff_games": [g.id for g in finished if g.row.type == "playoff"]}


# ------------------------------------------------------------------ calendars (always the current season)

def _calendars(league: League, data: LoadedData, ctxs: dict[str, SeasonCtx], site_url: str) -> dict:
    """calendar/*.ics and calendars.json, from the `current` season (even when the site shows the sample)."""
    empty = {"json": {"season": None, "files": []}, "files": {}, "team_files": set()}
    current = next((c for c in ctxs.values() if c.loaded.season.current), None)
    if current is None or not current.loaded.schedule:
        return empty
    season = current.loaded.season
    games = [_cal_game(current, row) for row in current.game_rows()]
    files = build_calendars(
        league_name=league.name, season_label=season.label, timezone=league.timezone, game_minutes=league.game_minutes,
        games=games, teams={t.id: t.name for t in current.teams.values()}, site_url=site_url,
        address=season.venue_address or "", today=current.today)
    entries = [links(LEAGUE_FILE, "Whole league", None, site_url)]
    entries += [links(f"{t.id}.ics", t.name, t.id, site_url) for t in current.teams.values()]
    return {"json": {"season": season.id, "files": entries}, "files": files,
            "team_files": {t.id for t in current.teams.values()}}


def _cal_game(ctx: SeasonCtx, row: ScheduleRow) -> CalGame:
    score = final_score(ctx, row.game_id)
    result = None
    if score is not None:
        game = ctx.loaded.games[row.game_id]
        text = f"{ctx.team_name(row.home)} {score[0]}, {ctx.team_name(row.away)} {score[1]}"
        result = (f"Forfeit: {ctx.team_name(game.forfeit or '')} forfeited. {text}." if game.forfeit
                  else f"Final: {text}.")
    venue = ctx.venue_of(row)
    return CalGame(row.game_id, row.date, row.time, row.home, row.away, ctx.team_name(row.home),
                   ctx.team_name(row.away), row.teams_known, row.type, row.round, row.cancelled, row.moved_from,
                   venue, venue == (ctx.loaded.season.venue or ""), result)


# ------------------------------------------------------------------ one season's files

def _season_files(out: BuildOutput, ctx: SeasonCtx, calendar_teams: set[str]) -> None:
    players, leaders = build_stats(ctx)
    standings = _standings(ctx)
    schedule = _schedule(ctx)
    out.data[f"{ctx.sid}/teams.json"] = _teams(ctx, calendar_teams)
    out.data[f"{ctx.sid}/standings.json"] = standings
    out.data[f"{ctx.sid}/schedule.json"] = schedule
    out.data[f"{ctx.sid}/results.json"] = _results(schedule)
    out.data[f"{ctx.sid}/games.json"] = build_games(ctx)
    out.data[f"{ctx.sid}/players.json"] = players
    out.data[f"{ctx.sid}/leaders.json"] = leaders


# ------------------------------------------------------------------ standings

def points_sentence(standings: dict, ties: bool, period_one: str) -> str:
    """'2 points a win, 1 a tie and 1 for an overtime loss.' (or the win-percentage rule)."""
    if standings["rank_by"] == "win_pct":
        return "Teams are ranked by winning percentage" + (" (a tie counts as half a win)." if ties else ".")
    p = standings["points"]
    parts = [f"{fmt.plural(p['win'], 'point')} a win"]
    if ties and p["tie"]:
        parts.append(f"{p['tie']} a tie")
    if p["loss"]:
        parts.append(f"{p['loss']} a loss")
    if p["ot_win"] != p["win"]:
        parts.append(f"{p['ot_win']} for an overtime win")
    if p["ot_loss"] != p["loss"]:
        parts.append(f"{p['ot_loss']} for an overtime loss")
    if standings["period_points"]:
        parts.append(f"{standings['period_points']} for each {period_one} won")
    return (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."


def standings_columns(ctx: SeasonCtx) -> list[dict]:
    spec, st = ctx.spec, ctx.settings.standings
    period = spec["words"]["period"]
    words = dict(COLUMN_WORDS)
    words["pf"] = (spec["words"]["points_for"]["label"], spec["words"]["points_for"]["title"])
    words["pa"] = (spec["words"]["points_against"]["label"], spec["words"]["points_against"]["title"])
    words["pw"] = (f"{period['short']}W", f"{period['many']} won")
    words.update({s["key"]: (s["label"], s["title"]) for s in spec["stats"].get("team", [])})
    key = "pct" if st["rank_by"] == "win_pct" else "pts"
    return [{"key": c, "label": words[c][0], "title": words[c][1], "key_col": c == key} for c in st["columns"]]


def _race_max(ctx: SeasonCtx) -> int:
    """Most points a team could have so far: the most games any team has played, all won with every period."""
    st = ctx.settings.standings
    best = max([st["points"]["win"], st["points"]["ot_win"]] + ([st["points"]["tie"]] if st["ties"] else []))
    games = max((len(g) for g in ctx.standing.results.values()), default=0)
    return games * (best + st["period_points"] * (ctx.regulation or 0))


def _race_row(ctx: SeasonCtx, row: dict, basis: str, maximum: int) -> dict:
    rec = record_of(ctx.regular_games(row["team"]), ctx.team_stat_keys())
    if basis == "win_pct":
        gb = row["display"].get("gb")
        sub = fmt.signed(rec.diff) + (f" · {gb} GB" if gb and gb != fmt.DASH else "")
        return {"pct": f"{float(rec.pct) * 100:.1f}", "value": record_text(rec), "unit": "", "sub": sub}
    pct = rec.pts / maximum * 100 if maximum else 0.0
    return {"pct": f"{pct:.1f}", "value": str(rec.pts), "unit": " points", "sub": record_text(rec)}


def _standings(ctx: SeasonCtx) -> dict:
    st = ctx.settings.standings
    basis = "win_pct" if st["rank_by"] == "win_pct" else "points"
    maximum = _race_max(ctx)
    note = " ".join(x for x in (points_sentence(st, st["ties"], ctx.spec["words"]["period"]["one"].lower()),
                                f"Playoffs: {st['playoffs']}" if st.get("playoffs") else "") if x)
    counted = [ctx.loaded.games[tg.game_id].row.date for games in ctx.standing.results.values() for tg in games]
    through = max(counted) if counted else None
    rows = [{**{k: v for k, v in r.items() if k != "record"}, "record": dash(r["record"]),
             "race": _race_row(ctx, r, basis, maximum)} for r in ctx.standing.rows]
    return {"columns": standings_columns(ctx), "rows": rows, "note": note, "tiebreak_note": ctx.standing.tiebreak_note,
            "through": through.isoformat() if through else None,
            "through_display": fmt.date_short(through) if through else None,
            "race": {"basis": basis, "max": maximum if basis == "points" else None}}


# ------------------------------------------------------------------ teams

def _teams(ctx: SeasonCtx, calendar_teams: set[str]) -> dict:
    by_team = {r["team"]: r for r in ctx.standing.rows}
    points_shown = ctx.settings.standings["rank_by"] == "points"
    finished = ctx.finished()
    pending = [r for r in ctx.game_rows() if r.teams_known and not r.cancelled and r.game_id not in ctx.loaded.games
               and r.date >= ctx.today]
    out = {}
    for team in ctx.teams.values():
        row = by_team.get(team.id)
        rec = record_of(ctx.regular_games(team.id), ctx.team_stat_keys())
        out[team.id] = {
            "id": team.id, "name": team.name, "code": team.code, "slot": team.slot, "colour": team.colour,
            "url": team_url(team.id) if ctx.active else None, "rank": row["rank"] if row else None,
            "record": dash(rec.text), "points": str(rec.pts) if points_shown else None, "sub": None,
            "players": [p.id for p in ctx.players.values() if p.team == team.id],
            "results": [g.id for g in reversed(finished) if team.id in (g.home, g.away)],
            "upcoming": [r.game_id for r in pending if team.id in (r.home, r.away)],
            "calendar": f"/calendar/{team.id}.ics" if team.id in calendar_teams else None,
        }
    return out


# ------------------------------------------------------------------ schedule and results

def _row_json(ctx: SeasonCtx, row: ScheduleRow) -> dict:
    game = ctx.loaded.games.get(row.game_id)
    score = final_score(ctx, row.game_id) if game else None
    winner = None
    if score and score[0] != score[1]:
        winner = "home" if score[0] > score[1] else "away"
    status = "cancelled" if row.cancelled else "played" if game else "scheduled"
    return {
        "id": row.game_id, "url": game_url(row.game_id) if game else None, "time_display": ctx.time_display(row),
        "surface": row.surface, "surface_label": ctx.surface_label(row), "home": row.home, "away": row.away,
        "home_name": ctx.team_name(row.home), "away_name": ctx.team_name(row.away), "status": status,
        "moved_from_display": fmt.date_short(row.moved_from) if row.moved_from else None, "round": row.round,
        "played": game is not None, "score": {"home": score[0] if score else None, "away": score[1] if score else None},
        "winner": winner, "teams_known": row.teams_known, "tie": bool(score and score[0] == score[1]),
    }


def _state(ctx: SeasonCtx, rows: list[ScheduleRow]) -> str:
    live = [r for r in rows if not r.cancelled]
    if not live:
        return "cancelled"
    done = sum(r.game_id in ctx.loaded.games for r in live)
    return "played" if done == len(live) else "partial" if done else "upcoming"


def _all_pm(ctx: SeasonCtx) -> bool:
    rows = ctx.loaded.schedule
    return ctx.league.time_format == "12h" and bool(rows) and all(r.time.hour >= 12 for r in rows)


def _foot(ctx: SeasonCtx, kind: str, byes: list[str], all_pm: bool) -> str:
    """The line under the next-game panel: the bye ("Herons have the bye"), led by "All times PM." when it applies.
    On the Scoreboard layout a bye with nothing else to say is left empty, so the include draws "Bye: <b>Herons</b>"."""
    pm = "All times PM." if all_pm else ""
    if kind != "regular":
        return pm
    if not byes:
        return f"{pm} No bye this week.".strip()
    names = ", ".join(ctx.team_name(b) for b in byes[:-1]) + (" and " if len(byes) > 1 else "") + ctx.team_name(byes[-1])
    if ctx.league.layout == "scoreboard":
        return f"{pm} Bye: {names}".strip() if pm else ""
    return f"{pm} {names} have the bye".strip()


def _groups(ctx: SeasonCtx, games: list[dict]) -> list[dict]:
    """The Curling layout draws a day's games in groups by start time; every other layout, one group."""
    if ctx.league.layout != "curling":
        return [{"time_label": None, "games": games}]
    out: list[dict] = []
    for g in games:
        if not out or out[-1]["time_label"] != g["time_display"]:
            out.append({"time_label": g["time_display"], "games": []})
        out[-1]["games"].append(g)
    return out


def _day(ctx: SeasonCtx, n: int, date: dt.date, kind: str, rows: list[ScheduleRow], all_pm: bool) -> dict:
    games = [_row_json(ctx, r) for r in rows]
    venues = list(dict.fromkeys(v for v in (ctx.venue_of(r) for r in rows) if v))
    label = ctx.day_label(rows)
    byes = list(ctx.loaded.byes.get(date, ())) if kind == "regular" else []
    return {
        "n": n, "label": label, "date": date.isoformat(), "date_short": fmt.date_short(date),
        "date_long": fmt.date_long(date), "type": kind, "venues": venues, "state": _state(ctx, rows),
        "games": games, "byes": byes, "eyebrow": label,
        "where": " · ".join(x for x in (", ".join(venues), label) if x),
        "foot": _foot(ctx, kind, byes, all_pm), "foot_link": None, "groups": _groups(ctx, games),
    }


def _schedule(ctx: SeasonCtx) -> dict:
    """The days (regular and playoff kept apart), the latest day with a result and the next one to play."""
    all_pm = _all_pm(ctx)
    days = [_day(ctx, n, d, kind, rows, all_pm) for n, (d, kind, rows) in enumerate(ctx.days(), start=1)]
    latest = next((d["n"] for d in reversed(days) if d["state"] in ("played", "partial")), None)
    nxt = next((d["n"] for d in days if d["date"] >= ctx.today.isoformat() and any(
        not g["played"] and g["status"] != "cancelled" for g in d["games"])), None)
    if nxt is not None:
        days[nxt - 1]["eyebrow"] = league_labels(ctx.league)["next"]
    return {"days": days, "latest": latest, "next": nxt, "all_times_pm": all_pm}


def _results(schedule: dict) -> list[dict]:
    """The days with a result, newest first: {day: n, games: [ids that were played]}."""
    return [{"day": d["n"], "games": [g["id"] for g in d["games"] if g["played"]]}
            for d in reversed(schedule["days"]) if any(g["played"] for g in d["games"])]


# ------------------------------------------------------------------ stub pages

def _season_pages(out: BuildOutput, ctx: SeasonCtx) -> None:
    games = out.data[f"{ctx.sid}/games.json"]
    for gid, g in games.items():
        out.pages.setdefault("_games", {})[f"{gid}.md"] = {
            "season": ctx.sid, "game_id": gid, "title": f"{g['home']['name']} vs {g['away']['name']}",
            "description": f"{g['final']['status']}: {g['home']['name']} {g['home']['score']}, "
                           f"{g['away']['name']} {g['away']['score']} on {g['date_long']}."}
    if ctx.active:
        _active_pages(out, ctx)
    else:
        out.pages.setdefault("_archive", {})[f"{ctx.sid}.md"] = {
            "season": ctx.sid, "title": f"{ctx.label} season",
            "description": f"Standings, results and stats from the {ctx.label} season."}


def _active_pages(out: BuildOutput, ctx: SeasonCtx) -> None:
    teams = out.data[f"{ctx.sid}/teams.json"]
    for tid, t in teams.items():
        out.pages.setdefault("_teams", {})[f"{tid}.md"] = {
            "season": ctx.sid, "team_id": tid, "title": t["name"],
            "description": f"{t['name']}: record {t['record']}, No. {t['rank']} in the standings."}
    for pid, p in out.data[f"{ctx.sid}/players.json"].items():
        out.pages.setdefault("_players", {})[f"{pid}.md"] = {
            "season": ctx.sid, "player_id": pid, "title": p["label"],
            "description": f"Season totals and game log for {p['name']}"
                           + (f" of the {p['team_name']}." if p["team_name"] else "" if p["name"].endswith(".") else ".")}
