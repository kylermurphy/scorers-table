"""One season, ready to compute from: the loaded data plus the standings and every game's result per team.

`build_ctx()` runs the standings engine once and keeps what the other compute modules share (the results of
every game, the running record after each game, the names, the site paths), so no other module works out a
result or a record on its own. Nothing here writes a file or reads the clock.

Choices (each also in the build report):
* Results of all games, playoff games included, come from `standings.game_results()`; the engine's own
  `.results` holds regular-season games only. A game's problems (a tie where none is allowed...) are reported
  once, by `compute_standings`, so the copies from `game_results()` are dropped here.
* A record is written with an en dash ("5–2", "5–1–1"), as in the design mockups; the engine's text uses a hyphen.
* A `per_period` forfeit needs the number of regulation periods from `sports.regulation_periods`; when the sport
  does not say, a season that has such a forfeit gets one error that names sport.yml.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from scripts.core import fmt
from scripts.core.loader import LoadedGame, LoadedSeason, ScheduleRow
from scripts.core.model import League, Placeholder, Player, Problem, Team
from scripts.core.sports import regulation_periods
from scripts.core.standings import (
    Record, StandingsGame, StandingsResult, TeamGame, compute_standings, game_results, record_of,
)

# Site paths (for `relative_url`): leading slash, trailing slash.
GAMES_PATH, PLAYERS_PATH, TEAMS_PATH, ARCHIVE_PATH = "/games/", "/players/", "/teams/", "/archive/"


def game_url(game_id: str) -> str:
    return f"{GAMES_PATH}{game_id}/"


def player_url(player_id: str) -> str:
    return f"{PLAYERS_PATH}{player_id}/"


def team_url(team_id: str) -> str:
    return f"{TEAMS_PATH}{team_id}/"


def archive_url(season_id: str) -> str:
    return f"{ARCHIVE_PATH}{season_id}/"


# Section labels the core supplies when neither the sport nor league.yml words them. The Scoreboard layout words
# three of them its own way (the design mockups); a sport's own `labels` (and `labels_by_layout`) win over these.
BASE_LABELS = {"standings": "Standings", "full_table": "Full table", "all_stats": "All stats", "team": "Team",
               "final": "Final", "tie": "Tie", "featured": "Game of the week"}
SCOREBOARD_LABELS = {"standings": "The race", "full_table": "Full standings", "all_stats": "All player stats"}


def league_labels(league: League) -> dict[str, str]:
    """The labels pages use: the core's, then the layout's, then the sport's and league.yml's (League.labels)."""
    layout = SCOREBOARD_LABELS if league.layout == "scoreboard" else {}
    return {**BASE_LABELS, **layout, **league.labels}


def dash(text: str) -> str:
    """'5-1-1' -> '5–1–1' (an en dash between the numbers of a record or a score)."""
    return text.replace("-", "–")


def record_text(record: Record) -> str:
    return dash(record.text)


@dataclass
class SeasonCtx:
    """Everything the compute modules read about one season."""
    league: League
    loaded: LoadedSeason
    active: bool                                   # the season every page shows (its team and player pages exist)
    regulation: int | None                         # regulation periods per game, None when the sport did not say
    games: list[StandingsGame]
    standing: StandingsResult
    results: dict[str, dict[str, TeamGame]]        # game id -> team id -> TeamGame (every game, playoffs too)
    after: dict[tuple[str, str], Record] = field(default_factory=dict)    # (game id, team) -> record after that game
    problems: list[Problem] = field(default_factory=list)

    # -- shortcuts
    @property
    def sid(self) -> str:
        return self.loaded.season.id

    @property
    def label(self) -> str:
        return self.loaded.season.label

    @property
    def spec(self) -> dict:
        return self.league.sport_def.spec

    @property
    def settings(self):
        return self.loaded.settings

    @property
    def teams(self) -> dict[str, Team]:
        return self.loaded.teams

    @property
    def players(self) -> dict[str, Player]:
        return self.loaded.players

    @property
    def today(self) -> dt.date:
        return self.loaded.today

    @property
    def placeholders(self) -> tuple[Placeholder, ...]:
        return self.settings.placeholders

    def is_placeholder(self, setting: str) -> bool:
        return any(p.setting == setting for p in self.placeholders)

    # -- names and words
    def team_name(self, team: str) -> str:
        """A team's name; on a playoff row whose teams are not known yet, the text as written ('1st')."""
        found = self.teams.get(team)
        return found.name if found else team

    def venue_of(self, row: ScheduleRow) -> str:
        return row.venue or self.loaded.season.venue or ""

    def surface_label(self, row: ScheduleRow) -> str | None:
        word = self.spec["words"].get("surface", "")
        return f"{word} {row.surface}" if word and row.surface else None

    def time_display(self, row: ScheduleRow) -> str:
        return fmt.format_time(row.time, self.league.time_format)

    def day_label(self, rows: list[ScheduleRow]) -> str:
        """'Week 3' for a regular-season day (the sport's word for a game day); a playoff day is its round."""
        first = rows[0]
        if first.type == "playoff":
            rounds = {r.round for r in rows if r.round}
            return rounds.pop() if len(rounds) == 1 else "Playoffs"
        return f"{self.spec['words']['day']} {first.week}" if first.week else ""

    # -- games
    def game_rows(self) -> list[ScheduleRow]:
        """Every schedule row, in date, time, game id order."""
        return sorted(self.loaded.schedule, key=lambda r: (r.date, r.time, r.game_id))

    def days(self) -> list[tuple[dt.date, str, list[ScheduleRow]]]:
        """The game days: (date, type, rows). A date with regular and playoff games is two days, regular first;
        rows are in time, game id order."""
        groups: dict[tuple[dt.date, str], list[ScheduleRow]] = {}
        for row in self.game_rows():
            groups.setdefault((row.date, row.type), []).append(row)
        return [(d, kind, rows) for (d, kind), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] != "regular"))]

    def finished(self) -> list[LoadedGame]:
        """The games with a score sheet or a forfeit, in date, time, game id order."""
        return sorted(self.loaded.games.values(), key=lambda g: (g.row.date, g.row.time, g.id))

    def record_after(self, game_id: str, team: str) -> Record:
        """The team's regular-season record through that game; for a playoff game, its final regular record."""
        found = self.after.get((game_id, team))
        if found is not None:
            return found
        return record_of(self.regular_games(team), self.team_stat_keys())

    def regular_games(self, team: str) -> list[TeamGame]:
        return list(self.standing.results.get(team, []))

    def team_stat_keys(self) -> list[str]:
        return [s["key"] for s in self.spec["stats"].get("team", [])]


# ------------------------------------------------------------------ building it

def standings_game(game: LoadedGame) -> StandingsGame:
    return StandingsGame(game.id, game.home, game.away, game.reading, game.row.type, game.forfeit, game.file)


def build_ctx(league: League, loaded: LoadedSeason, *, active: bool) -> SeasonCtx:
    """Run the standings for one season. Problems (ties where none are allowed...) are collected, not raised."""
    standings = loaded.settings.standings
    reg = regulation_periods(league.sport_def.spec, loaded.settings.rules)
    games = [standings_game(g) for g in loaded.games.values()]
    problems: list[Problem] = []
    if reg is None and games and standings["forfeit"]["score"] == "per_period" and any(g.forfeit for g in games):
        problems.append(Problem("error", "line_score.periods",
                                "The standings give a forfeit 1-0 in every period, but this sport does not say how "
                                "many periods a game has. Add 'periods:' under line_score (a number, or the name of "
                                "a number option like 'periods').", f"sports/{league.sport}/sport.yml"))
        reg = 1                                  # so the table can still be worked out; the build stops anyway
    reg_for_engine = reg if reg is not None else 1
    unset = any(p.setting == "standings.tiebreakers" for p in loaded.settings.placeholders)
    standing = compute_standings(games, loaded.teams, standings, regulation_periods=reg_for_engine,
                                 tiebreakers_unset=unset)
    problems.extend(standing.problems)
    results: dict[str, dict[str, TeamGame]] = {}
    for g in games:
        counted, _ = game_results(g, standings, reg_for_engine)       # its problems are in standing.problems
        if counted is not None:
            results[g.game_id] = counted
    ctx = SeasonCtx(league, loaded, active, reg, games, standing, results, {}, problems)
    ctx.after = _running_records(ctx)
    return ctx


def _running_records(ctx: SeasonCtx) -> dict[tuple[str, str], Record]:
    """The record of each team after each of its regular-season games, in date, time, game id order."""
    order = {g.id: (g.row.date, g.row.time, g.id) for g in ctx.loaded.games.values()}
    stat_keys = ctx.team_stat_keys()
    out: dict[tuple[str, str], Record] = {}
    for team, games in ctx.standing.results.items():
        so_far: list[TeamGame] = []
        for tg in sorted(games, key=lambda x: order.get(x.game_id, (dt.date.min, dt.time.min, x.game_id))):
            so_far.append(tg)
            out[(tg.game_id, team)] = record_of(so_far, stat_keys)
    return out


def final_score(ctx: SeasonCtx, game_id: str) -> tuple[int, int] | None:
    """(home, away) final score of a finished game, forfeits included; None when it cannot be counted."""
    counted = ctx.results.get(game_id)
    game = ctx.loaded.games.get(game_id)
    if not counted or game is None:
        return None
    return counted[game.home].pf, counted[game.away].pf


def result_word(result: str) -> str:
    """'win' -> 'Win', 'ot_loss' -> 'Loss' (the overtime is said elsewhere)."""
    return {"win": "Win", "ot_win": "Win", "loss": "Loss", "ot_loss": "Loss", "tie": "Tie"}.get(result, result.title())
