"""The standings engine (docs/stage-4-spec.md, section 3.5): pure functions from game results to a table.

No file reading, no globals that change, no clock: the same games always give the same rows, whatever order
they come in. The loader turns each game file into a `StandingsGame` (who played, the sport's `Reading`, or the
team that forfeited); the build calls `compute_standings()` once per season and writes the rows into
`standings.json` (spec 4.1). `results_by_team()` gives the same per-team, per-game results for the game and
team pages ("standings points earned in this game"), so no other module works out a result.

The `standings` argument is the merged settings from `config.normalise_standings` / `effective_settings`:
rank_by, points (win tie loss ot_win ot_loss), period_points, ties, forfeit, tiebreakers, columns.

Choices where the spec leaves room (also in the docstrings that use them):
* `w` counts every win, overtime wins included, and `l` every loss (so a Masters-style table with no `otw`
  column is right); `otw` and `otl` are the "of which" overtime counts. `gp` = w + l + t.
* A fixed-score forfeit earns no period points (it has no periods); `per_period` earns all of them.
* A game that is an error (tied when it may not be, no final score, a team playing itself, a game id listed
  twice, a team outside the season) is left out of the table and reported (the build stops anyway).
* Ranks are competition ranks: 1, 2, 2, 4 (teams level share a rank; the next rank skips).
* Games behind are counted from the leader; when several teams share first place, from the one with the best
  wins-minus-losses, so no co-leader is shown ahead of "—".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Iterable, Mapping

from scripts.core import fmt
from scripts.core.model import Problem, Reading, Team
from scripts.core.problems import join_path

# The columns the engine works out itself; any other name in `columns` is a sport team stat (sport.yml
# stats.team), summed from Reading.team_lines.
KNOWN_COLUMNS = ("gp", "w", "l", "t", "otw", "otl", "pts", "pct", "pf", "pa", "diff", "gb", "pw")
RESULTS = ("win", "loss", "tie", "ot_win", "ot_loss")
WIN_RESULTS = ("win", "ot_win")
LOSS_RESULTS = ("loss", "ot_loss")


# ------------------------------------------------------------------ input and per-game output

@dataclass(frozen=True)
class StandingsGame:
    """One game as the standings need it (the loader builds these from schedule row + game file)."""
    game_id: str
    home: str                          # team ids
    away: str
    reading: Reading | None            # the sport's reading of the sheet; None for a forfeit
    type: str = "regular"              # "regular" | "playoff"
    forfeit: str | None = None         # the team id that forfeited
    file: str = ""                     # the game file, for problems ("data/2026-27/games/2026-11-05-1.yml")


@dataclass(frozen=True)
class TeamGame:
    """One team's side of one counted game."""
    game_id: str
    team: str
    opponent: str
    side: str                          # "home" | "away"
    result: str                        # win | loss | tie | ot_win | ot_loss
    points: int                        # standings points earned: points[result] + period_points x periods_won
    pf: int
    pa: int
    periods_won: int
    forfeit: bool = False              # this game was a forfeit (either side)
    stats: Mapping[str, int] = field(default_factory=dict)    # the sport's team stats for this game

    @property
    def margin(self) -> int:
        return self.pf - self.pa


@dataclass
class StandingsResult:
    rows: list[dict]                   # spec 4.1 rows, in table order
    tiebreak_note: str
    results: dict[str, list[TeamGame]]    # per team id, by game id (regular season only)
    problems: list[Problem]


# ------------------------------------------------------------------ one game -> a result per team

def _final_at(game: StandingsGame) -> str:
    final_at = game.reading.score.final_at if game.reading else {}
    return final_at.get("home") or next(iter(final_at.values()), "")


def game_results(game: StandingsGame, standings: Mapping[str, Any], regulation_periods: int
                 ) -> tuple[dict[str, TeamGame] | None, list[Problem]]:
    """The `TeamGame` of each team in one game ({team id: TeamGame}), and the problems. The dict is None when
    the game cannot be counted (a tied game that may not be tied, a missing score, a bad forfeit, a team
    playing itself).

    A tied playoff game is always an error; a tied regular-season game is an error when `ties` is false; both
    are reported once, at the Final box of the home side (`Score.final_at`), with the game's file name."""
    def problem(at: str, message: str) -> list[Problem]:
        return [Problem("error", at, message, game.file)]

    if game.home == game.away:
        return None, problem("away", f"{game.home!r} cannot play itself; check the home and away teams.")
    if game.forfeit is not None:
        if game.forfeit not in (game.home, game.away):
            return None, problem("forfeit", f"{game.forfeit!r} did not play in this game; "
                                 f"name {game.home!r} or {game.away!r}.")
        return _forfeit_results(game, standings, regulation_periods), []
    if game.reading is None:
        return None, problem("", "This game has neither a score sheet nor a forfeit.")
    score = game.reading.score
    home, away = score.final.get("home"), score.final.get("away")
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (home, away)):
        return None, problem(_final_at(game), "This game has no final score for both sides; fill in the Final boxes.")
    if home == away:
        if game.type == "playoff":
            return None, problem(_final_at(game), f"A playoff game cannot end tied ({home}-{away}); "
                                 "check the Final boxes and the overtime boxes.")
        if not standings["ties"]:
            return None, problem(_final_at(game), f"This league does not allow tied games, but this one ended "
                                 f"{home}-{away}; check the Final boxes and the overtime boxes.")
    won = {"home": 0, "away": 0}
    for h, a in zip(score.periods["home"], score.periods["away"]):
        if h is not None and a is not None and h != a:          # a tied or unplayed period gives nobody a point
            won["home" if h > a else "away"] += 1
    if home == away:
        results = {"home": "tie", "away": "tie"}
    else:
        winner, loser = ("home", "away") if home > away else ("away", "home")
        overtime = score.decided_in != "regulation"
        results = {winner: "ot_win" if overtime else "win", loser: "ot_loss" if overtime else "loss"}
    return _team_games(game, standings, results, final={"home": home, "away": away}, won=won), []


def _forfeit_results(game: StandingsGame, standings: Mapping[str, Any], regulation_periods: int
                     ) -> dict[str, TeamGame]:
    winner_side = "away" if game.forfeit == game.home else "home"
    loser_side = "home" if winner_side == "away" else "away"
    score = standings["forfeit"]["score"]
    if score == "per_period":
        final, won = {winner_side: regulation_periods, loser_side: 0}, {winner_side: regulation_periods, loser_side: 0}
    else:
        final, won = {winner_side: score[0], loser_side: score[1]}, {"home": 0, "away": 0}
    return _team_games(game, standings, {winner_side: "win", loser_side: "loss"}, final=final, won=won)


def _team_games(game: StandingsGame, standings: Mapping[str, Any], results: Mapping[str, str],
                final: Mapping[str, int], won: Mapping[str, int]) -> dict[str, TeamGame]:
    team_lines = game.reading.team_lines if game.reading else {}
    ids = {"home": game.home, "away": game.away}
    out = {}
    for side, other in (("home", "away"), ("away", "home")):
        points = standings["points"][results[side]] + standings["period_points"] * won[side]
        out[ids[side]] = TeamGame(
            game_id=game.game_id, team=ids[side], opponent=ids[other], side=side, result=results[side],
            points=points, pf=final[side], pa=final[other], periods_won=won[side],
            forfeit=game.forfeit is not None, stats=dict(team_lines.get(side, {})))
    return out


def results_by_team(games: Iterable[StandingsGame], teams: Iterable[str], standings: Mapping[str, Any],
                    regulation_periods: int) -> tuple[dict[str, list[TeamGame]], list[Problem]]:
    """{team id: [TeamGame, ...]} for every team in `teams`, from the regular-season games only, in game id
    order, plus the problems of every game (playoff games are checked for ties but never counted). A game that
    cannot be counted is left out. Games that name a team outside `teams` are an error, and so is a game id
    given more than once (none of its copies is counted)."""
    if regulation_periods < 1:
        raise ValueError("regulation_periods must be at least 1")
    known = set(teams)
    by_team: dict[str, list[TeamGame]] = {t: [] for t in sorted(known)}
    problems: list[Problem] = []
    games = sorted(games, key=lambda g: (g.game_id, g.file, g.home, g.away))
    seen: dict[str, int] = {}
    for game in games:
        seen[game.game_id] = seen.get(game.game_id, 0) + 1
    for game in games:
        if seen[game.game_id] > 1:
            problems.append(Problem("error", "game_id", f"Game {game.game_id!r} is given {seen[game.game_id]} times; "
                                    "each game id must be used once.", game.file))
            continue
        counted, found = game_results(game, standings, regulation_periods)
        problems.extend(found)
        if game.type != "regular" or counted is None:
            continue
        stranger = next((t for t in (game.home, game.away) if t not in known), None)
        if stranger is not None:
            problems.append(Problem("error", "home" if stranger == game.home else "away",
                                    f"{stranger!r} is not a team of this season.", game.file))
            continue
        for team, team_game in counted.items():
            by_team[team].append(team_game)
    return by_team, problems


# ------------------------------------------------------------------ one team's totals

@dataclass(frozen=True)
class Record:
    gp: int = 0
    w: int = 0
    l: int = 0
    t: int = 0
    otw: int = 0
    otl: int = 0
    pts: int = 0
    pf: int = 0
    pa: int = 0
    pw: int = 0
    stats: Mapping[str, int] = field(default_factory=dict)

    @property
    def diff(self) -> int:
        return self.pf - self.pa

    @property
    def pct(self) -> Fraction:
        """Wins over games, a tie counting as half a win."""
        return Fraction(2 * self.w + self.t, 2 * self.gp) if self.gp else Fraction(0)

    @property
    def text(self) -> str:
        return f"{self.w}-{self.l}" + (f"-{self.t}" if self.t else "")


def record_of(games: Iterable[TeamGame], stat_keys: Iterable[str] = ()) -> Record:
    games = list(games)
    count = lambda *kinds: sum(g.result in kinds for g in games)       # noqa: E731
    return Record(
        gp=len(games), w=count(*WIN_RESULTS), l=count(*LOSS_RESULTS), t=count("tie"), otw=count("ot_win"),
        otl=count("ot_loss"), pts=sum(g.points for g in games), pf=sum(g.pf for g in games),
        pa=sum(g.pa for g in games), pw=sum(g.periods_won for g in games),
        stats={k: sum(g.stats.get(k, 0) for g in games) for k in stat_keys})


@dataclass(frozen=True)
class Table:
    """What a tiebreaker may look at."""
    records: Mapping[str, Record]
    games: Mapping[str, tuple[TeamGame, ...]]

    def among(self, team: str, group: Iterable[str]) -> list[TeamGame]:
        """`team`'s games against the other teams of `group`."""
        others = set(group) - {team}
        return [g for g in self.games[team] if g.opponent in others]


# ------------------------------------------------------------------ the tiebreakers

# Each takes (table, group of tied team ids, **options) and returns {team id: key} (higher is better), or
# None to be skipped for this group.
Breaker = Callable[..., "dict[str, Fraction | int] | None"]


def _have_all_met(table: Table, group: list[str]) -> bool:
    return all(any(g.opponent == other for g in table.games[team])
               for team in group for other in group if other != team)


def _head_to_head(table: Table, group: list[str]) -> dict[str, Fraction] | None:
    """Win % in the games among the tied teams (a tie is half a win); skipped unless every pair has met."""
    if not _have_all_met(table, group):
        return None
    out = {}
    for team in group:
        r = record_of(table.among(team, group))
        out[team] = r.pct
    return out


def _head_to_head_points(table: Table, group: list[str]) -> dict[str, Fraction] | None:
    """Standings points per game in the games among the tied teams; same skip rule."""
    if not _have_all_met(table, group):
        return None
    out = {}
    for team in group:
        games = table.among(team, group)
        out[team] = Fraction(sum(g.points for g in games), len(games))
    return out


def _wins(table: Table, group: list[str]) -> dict[str, int]:
    return {t: table.records[t].w for t in group}


def _win_pct(table: Table, group: list[str]) -> dict[str, Fraction]:
    return {t: table.records[t].pct for t in group}


def _diff(table: Table, group: list[str], cap: int | None = None) -> dict[str, int]:
    """Points for minus against; with `cap`, each game's margin counts at most `cap` either way."""
    if cap is None:
        return {t: table.records[t].diff for t in group}
    return {t: sum(max(-cap, min(cap, g.margin)) for g in table.games[t]) for t in group}


def _points_for(table: Table, group: list[str]) -> dict[str, int]:
    return {t: table.records[t].pf for t in group}


def _points_against(table: Table, group: list[str]) -> dict[str, int]:
    return {t: -table.records[t].pa for t in group}            # fewer is better


def _periods_won(table: Table, group: list[str]) -> dict[str, int]:
    return {t: table.records[t].pw for t in group}


TIEBREAKERS: dict[str, Breaker] = {
    "head_to_head": _head_to_head,
    "head_to_head_points": _head_to_head_points,
    "wins": _wins,
    "win_pct": _win_pct,
    "diff": _diff,
    "points_for": _points_for,
    "points_against": _points_against,
    "periods_won": _periods_won,
}

# How each reads in the note under the table, and the short label on a row ("tiebreak").
_PHRASES = {
    "head_to_head": ("head-to-head record", "head-to-head"),
    "head_to_head_points": ("points in head-to-head games", "head-to-head points"),
    "wins": ("wins", "wins"),
    "win_pct": ("win percentage", "win percentage"),
    "diff": ("score difference", "score difference"),
    "points_for": ("points for", "points for"),
    "points_against": ("fewest points against", "points against"),
    "periods_won": ("periods won", "periods won"),
}


def normalise_tiebreakers(spec: Any) -> list[tuple[str, dict]]:
    """[(name, options)] from the settings list: 'wins' -> ('wins', {}); {'diff': {'cap': 7}} -> ('diff', {'cap': 7}).
    Raises ValueError on anything `validate_tiebreakers` would report."""
    problems = validate_tiebreakers(spec)
    if problems:
        raise ValueError(f"{problems[0].at}: {problems[0].message}")
    out = []
    for item in spec:
        if isinstance(item, dict):
            (name, options), = item.items()
            out.append((name, dict(options or {})))
        else:
            out.append((item, {}))
    return out


def validate_tiebreakers(spec: Any, at: str = "standings.tiebreakers") -> list[Problem]:
    """Problems (errors, with a path under `at`) in a tiebreakers setting: it must be a list of names from
    `TIEBREAKERS`, with `diff` the only one that takes options (`{diff: {cap: N}}`, N a whole number from 1).
    For the config and loader to call; the core adds the file name."""
    def err(path: str, message: str) -> list[Problem]:
        return [Problem("error", path, message)]

    if not isinstance(spec, (list, tuple)):
        return err(at, "must be a list of tiebreaker names, like [head_to_head, wins].")
    names = ", ".join(TIEBREAKERS)
    problems: list[Problem] = []
    seen: list[str] = []
    for i, item in enumerate(spec):
        item_at = join_path(at, i)
        options: Any = None
        if isinstance(item, dict):
            if len(item) != 1:
                problems += err(item_at, "a tiebreaker with options is one name, like {diff: {cap: 7}}.")
                continue
            (name, options), = item.items()
            item_at = join_path(item_at, name)
        else:
            name = item
        if not isinstance(name, str) or name not in TIEBREAKERS:
            problems += err(item_at, f"{name!r} is not a tiebreaker. Use one of: {names}.")
            continue
        if name in seen:
            problems += err(item_at, f"{name!r} is listed twice; the second one could never break a tie.")
        seen.append(name)
        if isinstance(item, dict):
            if name != "diff":
                problems += err(item_at, f"{name!r} takes no options; write just '{name}'.")
            elif not isinstance(options, dict) or set(options) - {"cap"}:
                problems += err(item_at, "only 'cap' is allowed here, like {diff: {cap: 7}}.")
            elif "cap" in options and (not isinstance(options["cap"], int) or isinstance(options["cap"], bool)
                                       or options["cap"] < 1):
                problems += err(join_path(item_at, "cap"), "must be a whole number of 1 or more.")
    return problems


def forfeit_text(standings: Mapping[str, Any], period_one: str = "period") -> str:
    """How a forfeit is scored, in words: '20–0', or '1–0 in every quarter' (`period_one` is the sport's word)."""
    score = standings["forfeit"]["score"]
    return f"1–0 in every {period_one}" if score == "per_period" else f"{score[0]}–{score[1]}"


def tiebreak_phrases(standings: Mapping[str, Any]) -> list[str]:
    """The tiebreakers in order, as phrases ('head-to-head record (when they have all played each other)')."""
    phrases = []
    met_said = False
    for name, options in normalise_tiebreakers(standings["tiebreakers"]):
        text = _PHRASES[name][0]
        if name == "diff" and "cap" in options:
            text += f" (each game counted up to {options['cap']})"
        if name in ("head_to_head", "head_to_head_points") and not met_said:
            text += " (when they have all played each other)"          # the skip rule, said once
            met_said = True
        phrases.append(text)
    return phrases


def tiebreak_note(standings: Mapping[str, Any], unset: bool = False) -> str:
    """One sentence under the table: 'Teams level on points are ranked by head-to-head record (when they have
    all played each other), then wins; teams still level share a rank.' (It says "level on points", not
    "ties", so it is not read as tied games.) With `unset` (the league has not decided its tiebreakers) it
    starts with the [placeholder] wording and then says what the build is using instead."""
    phrases = tiebreak_phrases(standings)
    basis = "win percentage" if standings["rank_by"] == "win_pct" else "points"
    if phrases:
        note = f"Teams level on {basis} are ranked by {', then '.join(phrases)}; teams still level share a rank."
    else:
        note = f"Teams level on {basis} share a rank."
    return f"{fmt.PLACEHOLDER} The league has not decided its tiebreakers yet. {note}" if unset else note


# ------------------------------------------------------------------ ordering

def _order(table: Table, teams: Mapping[str, Team], standings: Mapping[str, Any]) -> list[tuple[list[str], str | None]]:
    """The table as cells, best first: (teams level with each other, the tiebreaker that separated them from
    the rest or None). Teams in one cell share a rank and are listed by name."""
    breakers = normalise_tiebreakers(standings["tiebreakers"])
    by_name = lambda ids: sorted(ids, key=lambda t: (teams[t].name.casefold(), t))      # noqa: E731

    def split(group: list[str], start: int) -> list[tuple[list[str], str | None]]:
        for i in range(start, len(breakers)):
            name, options = breakers[i]
            keys = TIEBREAKERS[name](table, group, **options)
            if keys is None or len(set(keys.values())) < 2:        # skipped, or it separates nobody
                continue
            cells: list[tuple[list[str], str | None]] = []
            for key in sorted(set(keys.values()), reverse=True):
                part = [t for t in group if keys[t] == key]
                cells.extend([(part, name)] if len(part) == 1 else split(part, i + 1))
            return cells
        return [(by_name(group), None)]

    key_of = (lambda t: table.records[t].pct) if standings["rank_by"] == "win_pct" else (lambda t: table.records[t].pts)
    cells: list[tuple[list[str], str | None]] = []
    for key in sorted({key_of(t) for t in teams}, reverse=True):
        group = [t for t in teams if key_of(t) == key]
        cells.extend([(group, None)] if len(group) == 1 else split(group, 0))
    return cells


# ------------------------------------------------------------------ the rows

def _gb(table: Table, leader: str, team: str) -> Fraction:
    """Games behind the leader: half the wins gap plus half the losses gap (a tie is half a win, half a loss,
    so ties cancel out). Negative for a team with a better wins-minus-losses than the leader (possible when
    the table is ranked by points, or by win % with unequal games)."""
    def wl(t: str) -> tuple[Fraction, Fraction]:
        r = table.records[t]
        return r.w + Fraction(r.t, 2), r.l + Fraction(r.t, 2)

    (lw, ll), (w, l) = wl(leader), wl(team)
    return ((lw - w) + (l - ll)) / 2


def _number(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


def _row_values(table: Table, leader: str, team: str, columns: Iterable[str]) -> tuple[dict, dict]:
    r = table.records[team]
    values: dict[str, Any] = {}
    display: dict[str, str] = {}
    for col in columns:
        if col == "pct":
            values[col], display[col] = fmt.round_half_up(r.pct, 3), fmt.win_pct(r.w, r.l, r.t)
        elif col == "diff":
            values[col], display[col] = r.diff, fmt.signed(r.diff)
        elif col == "gb":
            gap = _gb(table, leader, team)
            text = fmt.decimal(abs(float(gap)), 1).removesuffix(".0")
            values[col], display[col] = _number(gap), (fmt.DASH if gap == 0 else fmt.MINUS + text if gap < 0 else text)
        else:
            values[col] = getattr(r, col) if col in KNOWN_COLUMNS else r.stats.get(col, 0)
            display[col] = str(values[col])
    return values, display


def compute_standings(games: Iterable[StandingsGame], teams: Mapping[str, Team], standings: Mapping[str, Any],
                      *, regulation_periods: int, tiebreakers_unset: bool = False) -> StandingsResult:
    """The standings table of one season (spec 3.5 and 4.1).

    games: every game of the season, playoff games included (they are only checked for ties).
    teams: this season's teams by id; their names order teams that stay level.
    standings: the merged settings (`League.standings` or `effective_settings(...).standings`).
    regulation_periods: how many regulation periods a game has (the sport's `periods` rule, e.g. 4 quarters);
        a `per_period` forfeit is that many periods to none. sport.yml has no field for it, so the caller reads
        it from its rules (the stub's `periods`).
    tiebreakers_unset: the league left `standings.tiebreakers` undecided (a placeholder), so the note says so.

    Rows are plain dicts: {rank, team, values, display, record, tied, broke_by, tiebreak} with values/display
    holding the requested `columns`. `tied` is true when another team shares the rank; `broke_by` is the key
    of the tiebreaker that separated the team from the others level on points (None when the points did, or
    when the team is still level); `tiebreak` is that tiebreaker in words ("head-to-head")."""
    columns = list(standings["columns"])
    stat_keys = [c for c in columns if c not in KNOWN_COLUMNS]
    by_team, problems = results_by_team(games, teams, standings, regulation_periods)
    table = Table({t: record_of(g, stat_keys) for t, g in by_team.items()}, {t: tuple(g) for t, g in by_team.items()})
    cells = _order(table, teams, standings) if teams else []
    rows: list[dict] = []
    top = cells[0][0] if cells else []        # first place (shared or not); games behind count from its best record
    leader = max(top, key=lambda t: table.records[t].w - table.records[t].l) if top else ""
    for cell, broke_by in cells:
        rank = len(rows) + 1
        for team in cell:
            values, display = _row_values(table, leader, team, columns)
            rows.append({"rank": rank, "team": team, "values": values, "display": display,
                         "record": table.records[team].text, "tied": len(cell) > 1, "broke_by": broke_by,
                         "tiebreak": _PHRASES[broke_by][1] if broke_by else None})
    return StandingsResult(rows, tiebreak_note(standings, tiebreakers_unset), by_team, problems)
