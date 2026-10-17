#!/usr/bin/env python3
"""Write the made-up sample seasons for the league's sport (docs/stage-4-spec.md, section 3.6).

    python scripts/make_sample.py            # rewrite data/sample-*/ (every season in data/seasons.yml with `sample: true`)
    python scripts/make_sample.py --check    # change nothing; fail if the files on disk differ from what this would write

For each sample season it writes teams.yml, players.yml, schedule.csv, games/ and drafts/, from the sport's
`sports/<id>/sample.py` (team names and one function that writes a believable sheet) and a fixed seed, so two
runs give byte-identical files. The season has: a round robin, a cancelled game, a moved game (`moved_from`),
a forfeit, a tie where the rules allow one, one draft, game days still to come, and playoff rows with
placeholder teams. A season with `as_of` in seasons.yml is "today" on that date (games after it are not yet
played); a sample season without `as_of` is a finished past season (single round robin, playoffs played).

Every sheet is run through the sport's own `check` before it is written, and the finished folder through the
loader (when scripts/core/loader.py exists); any problem stops the script (exit 1). The one exception is the
draft: it is never built, it is where a volunteer fixes things, so a sport's sample may leave it a warning (a
sub written in by name, say). An error in a draft still stops the script.

Players are made-up "First L." names. Nothing here looks like a real league.

A sport's `sample.py` may set these optional constants (all of them default to what basketball needs):
`PLAYERS_PER_TEAM` (7), `TIMES` (the draw times, `["19:00", "20:15"]`: game number g of a day starts at
`TIMES[g % len(TIMES)]`), `SURFACES` (the court / sheet / rink names for a sport whose `words` has a `surface`:
game number g of a day plays on `SURFACES[g]`, default "1", "2"...), `NUMBERS` (True; False gives players no
jersey number), `POSITIONS` (none; a list of the sport's positions, written to players.yml in roster order: the
first player of a team gets the first, and so on) and `NOTES` (the free-text game notes some sheets carry).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import random
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.config import effective_settings, load_league      # noqa: E402
from scripts.core.fmt import parse_date                               # noqa: E402
from scripts.core.model import Player, SampleGame, SportContext, SportDef, Team   # noqa: E402
from scripts.core.problems import InternalError, call_sport, read_yaml   # noqa: E402
from scripts.core.sports import load_sport                            # noqa: E402

SEED = "scorers-table-sample-1"
HEADER = "# Made-up sample data, written by scripts/make_sample.py. Do not edit by hand: run the script again.\n"
CSV_COLUMNS = ["game_id", "date", "time", "home", "away", "venue", "surface", "type", "round", "week", "status",
               "moved_from"]
TIMES = ["19:00", "20:15"]
THURSDAY = 3
SPARES = 2
CHECKERS = ["Lee M.", "Pat S.", "Sam T."]
NOTES = ["Played with running time in the second half.", "Started ten minutes late."]

# Made-up first names; with one made-up initial each they make "First L." (nobody real).
FIRST_NAMES = ["Abe", "Ada", "Alf", "Amy", "Ben", "Bo", "Cal", "Cleo", "Dax", "Dee", "Eli", "Eve", "Finn", "Fay",
               "Gus", "Gwen", "Hal", "Hana", "Ike", "Ida", "Jax", "Joy", "Kai", "Kit", "Lars", "Lou", "Mae", "Max",
               "Nell", "Noa", "Oz", "Ola", "Pax", "Pia", "Quin", "Rae", "Sal", "Sky", "Tam", "Ted", "Uma", "Una",
               "Vic", "Val", "Wes", "Wren", "Yara", "Zed"]
INITIALS = "ABCDEFGHJKLMNPRSTW"


class SampleError(Exception):
    """The sample could not be made (a sheet failed its own sport's checks, bad seasons.yml...)."""


# ------------------------------------------------------------------ writing YAML

class Flow(dict):
    """A mapping written on one line: {home: [12, 9], away: [10, 10]}."""


class _Dumper(yaml.SafeDumper):
    """safe_dump quotes anything ambiguous ('no', '00', '2026-11-05'), which is what the strict loader wants."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


_Dumper.add_representer(Flow, lambda d, data: d.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True))
_Dumper.add_representer(list, lambda d, data: d.represent_sequence(
    "tag:yaml.org,2002:seq", data, flow_style=all(not isinstance(x, (dict, list)) for x in data)))


def dump_yaml(data) -> str:
    return HEADER + yaml.dump(data, Dumper=_Dumper, sort_keys=False, default_flow_style=False, width=10_000,
                              allow_unicode=True)


def flowify(node):
    """Mappings that hold no nested mapping or list of mappings are written on one line."""
    if isinstance(node, dict):
        simple = all(not isinstance(v, dict) and not (isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v))
                     for v in node.values())
        return Flow(node) if simple else {k: flowify(v) for k, v in node.items()}
    if isinstance(node, list):
        return [flowify(x) for x in node]
    return node


# ------------------------------------------------------------------ the pieces

def round_robin(ids: list[str]) -> list[list[tuple[str, str]]]:
    """The circle method: len-1 rounds (odd counts get a bye); home and away alternate."""
    teams: list[str | None] = list(ids)
    if len(teams) % 2:
        teams.append(None)
    n, rounds = len(teams), []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is not None and b is not None:
                pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds


def game_days(start: dt.date, count: int) -> list[dt.date]:
    days, day = [], start
    while len(days) < count:
        if (day.month, day.day) not in ((12, 24), (12, 31)):
            days.append(day)
        day += dt.timedelta(days=7)
    return days


def season_start(season_id: str) -> dt.date:
    """The first Thursday on or after 10 October of the year in the season id (sample-2026-27 -> 2026)."""
    match = re.search(r"\d{4}", season_id)
    if not match:
        raise SampleError(f"the sample season id {season_id!r} has no year in it (like sample-2026-27)")
    day = dt.date(int(match.group()), 10, 10)
    return day + dt.timedelta(days=(THURSDAY - day.weekday()) % 7)


def make_players(rng: random.Random, teams: list[Team], per_team: int, *, numbers: bool = True,
                 positions: list[str] | None = None) -> tuple[list[Player], dict[str, list[str]], list[str]]:
    """The made-up players: `per_team` regulars a team (the last one without a jersey number, the very first with
    "00", when `numbers` is on; no number at all when it is off), each with the position of the same place in
    `positions` when given, and SPARES players with no team."""
    pool = [(first, initial) for first in FIRST_NAMES for initial in INITIALS]
    picked = rng.sample(pool, per_team * len(teams) + SPARES)
    players: list[Player] = []
    roster: dict[str, list[str]] = {}
    for t, team in enumerate(teams):
        drawn = rng.sample(range(1, 100), per_team) if numbers else []
        roster[team.id] = []
        for k in range(per_team):
            first, initial = picked[t * per_team + k]
            number = (None if k == per_team - 1 else ("00" if (t, k) == (0, 0) else str(drawn[k]))) if numbers else None
            position = positions[k] if positions and k < len(positions) else None
            players.append(Player(f"{first.lower()}-{initial.lower()}", f"{first} {initial}.", team.id, number,
                                  position=position))
            roster[team.id].append(players[-1].id)
    spares = []
    for first, initial in picked[per_team * len(teams):]:
        players.append(Player(f"{first.lower()}-{initial.lower()}", f"{first} {initial}.", None, None, sub=True))
        spares.append(players[-1].id)
    return players, roster, spares


def player_rows(players: list[Player]) -> list:
    rows = []
    for p in players:
        row = {"id": p.id, "name": p.name, "team": p.team}
        if p.number is not None:
            row["number"] = int(p.number) if p.number != "00" else "00"
        if p.position is not None:
            row["position"] = p.position
        if p.sub:
            row["sub"] = True
        rows.append(Flow(row))
    return rows


@dataclass
class Row:
    """One schedule row while the season is being made."""
    game_id: str
    date: dt.date
    time: str
    home: str
    away: str
    surface: str = ""
    type: str = "regular"
    round: str = ""
    status: str = ""
    moved_from: str = ""
    forfeit_by: str | None = None
    forced: str | None = None
    draft: bool = False
    slot: str = ""                      # "sf1", "sf2", "final" for playoff rows

    def csv(self) -> list[str]:
        return [self.game_id, self.date.isoformat(), self.time, self.home, self.away, "", self.surface, self.type,
                self.round, "", self.status, self.moved_from]


def regular_rows(sport: SportDef, ids: list[str], start: dt.date, double: bool, *, times: list[str] = TIMES,
                 surfaces: list[str] | None = None) -> tuple[list[Row], list[list[Row]]]:
    """The round robin as schedule rows. Game g of a day starts at `times[g % len(times)]` and, for a sport with
    a surface word, plays on `surfaces[g]` (default "1", "2"...); two games of a day never share a surface."""
    rounds = round_robin(ids)
    if double:
        rounds = rounds + [[(b, a) for a, b in r] for r in rounds]
    surface_word = sport.spec["words"]["surface"]
    if surface_word and surfaces and max(len(r) for r in rounds) > len(surfaces):
        raise SampleError(f"SURFACES in sports/{sport.id}/sample.py names {len(surfaces)} {surface_word.lower()}s "
                          f"but {max(len(r) for r in rounds)} games are played on a day")
    by_round, rows = [], []
    for day, pairs in zip(game_days(start, len(rounds)), rounds):
        this = []
        for g, (home, away) in enumerate(pairs):
            surface = (surfaces[g] if surfaces else str(g + 1)) if surface_word else ""
            this.append(Row(f"{day.isoformat()}-{g + 1}", day, times[g % len(times)], home, away, surface=surface))
        by_round.append(this)
        rows.extend(this)
    return rows, by_round


def playoff_rows(sport: SportDef, last_day: dt.date, n_teams: int, *, times: list[str] = TIMES,
                 surfaces: list[str] | None = None) -> list[Row]:
    """The semifinals (the final only, with fewer than four teams) on the first two draw times and surfaces."""
    named = surfaces or ["1", "2"]
    surface = named[0] if sport.spec["words"]["surface"] else ""
    surface2 = named[1 % len(named)] if sport.spec["words"]["surface"] else ""
    time, time2 = times[0], times[1 % len(times)]
    semis, final = last_day + dt.timedelta(days=21), last_day + dt.timedelta(days=28)
    if n_teams >= 4:
        return [Row(f"{semis}-1", semis, time, "1st", "4th", surface, "playoff", "Semifinal", slot="sf1"),
                Row(f"{semis}-2", semis, time2, "2nd", "3rd", surface2, "playoff", "Semifinal", slot="sf2"),
                Row(f"{final}-1", final, time, "Winner SF1", "Winner SF2", surface, "playoff", "Final", slot="final")]
    return [Row(f"{final}-1", final, time, "1st", "2nd", surface, "playoff", "Final", slot="final")]


def pick_outcome(rng: random.Random, game_type: str, rules: dict, standings: dict, forced: str | None) -> str:
    """Which result to ask the sport for. "ot" is offered only when the league's `overtime` rule is on (any value
    but "none"); "tie" only for regular-season games when overtime is off and the standings allow ties."""
    overtime = rules.get("overtime", "none") not in ("none", None)
    tie_ok = game_type == "regular" and not overtime and standings.get("ties", True)
    if forced == "tie":
        forced = "ot" if overtime and game_type == "regular" else ("tie" if tie_ok else None)
    if forced:
        return forced
    names, weights = ["win_home", "win_away"], [4.0, 4.0]
    if overtime:
        names.append("ot"), weights.append(1.5)
    elif tie_ok:
        names.append("tie"), weights.append(1.0)
    return rng.choices(names, weights)[0]


def pick_players(rng: random.Random, roster: dict[str, list[str]], spares: list[str], home: str, away: str) -> dict[str, list[str]]:
    chosen, spare_used = {}, False
    for side, team in (("home", home), ("away", away)):
        regulars = roster[team]
        picked = set(rng.sample(regulars, rng.randint(min(5, len(regulars)), len(regulars))))
        ids = [p for p in regulars if p in picked]
        if spares and not spare_used and rng.random() < 0.12:
            ids.append(rng.choice(spares))
            spare_used = True
        chosen[side] = ids
    return chosen


# ------------------------------------------------------------------ one season

def sample_constants(sport: SportDef) -> dict:
    """The optional constants of sports/<id>/sample.py, checked, with their defaults."""
    sample, where = sport.sample, f"sports/{sport.id}/sample.py"

    def texts(name: str, default):
        value = getattr(sample, name, default)
        if value is default:
            return value
        if not (isinstance(value, (list, tuple)) and value and all(isinstance(v, str) and v for v in value)):
            raise SampleError(f"{name} in {where} must be a list of texts, like {default!r}")
        return list(value)

    times = texts("TIMES", TIMES)
    if not all(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t) for t in times):
        raise SampleError(f'TIMES in {where} must be times like "19:00"')
    positions = getattr(sample, "POSITIONS", None)
    if positions is not None:
        positions = texts("POSITIONS", None)
        allowed = sport.spec.get("positions") or []
        if not allowed:
            raise SampleError(f"POSITIONS in {where}, but sport.yml lists no positions")
        if any(p not in allowed for p in positions):
            raise SampleError(f"POSITIONS in {where} has a position that sport.yml does not list ({', '.join(allowed)})")
    numbers = getattr(sample, "NUMBERS", True)
    if not isinstance(numbers, bool):
        raise SampleError(f"NUMBERS in {where} must be True or False")
    return {"per_team": getattr(sample, "PLAYERS_PER_TEAM", 7), "times": times, "numbers": numbers,
            "surfaces": texts("SURFACES", None), "positions": positions, "notes": texts("NOTES", NOTES)}


def generate_season(sport: SportDef, season: dict, *, rules: dict, standings: dict, seed: str = SEED,
                    collect: list | None = None) -> dict[str, str]:
    """The files of one sample season as {path inside the season folder: text}. Raises SampleError when a sheet
    fails the sport's own checks. Pure apart from the sport's functions: the same arguments give the same text.
    `collect`, when given, receives a (sheet, context, SampleGame) for every sheet written (tests use it)."""
    if sport.sample is None:
        raise SampleError(f"sports/{sport.id}/sample.py was not loaded")
    sample, rules_mod = sport.sample, sport.rules
    rng = random.Random(f"{seed}:{season['id']}")
    as_of = parse_date(str(season["as_of"])) if season.get("as_of") else None
    teams = [Team(i, n, c, slot=k % 6 + 1) for k, (i, n, c) in enumerate(sample.TEAMS)]
    ids = [t.id for t in teams]
    const = sample_constants(sport)
    players, roster, spares = make_players(rng, teams, const["per_team"], numbers=const["numbers"],
                                           positions=const["positions"])
    team_map = {t.id: t for t in teams}
    player_map = {p.id: p for p in players}

    rows, by_round = regular_rows(sport, ids, season_start(season["id"]), double=as_of is not None,
                                  times=const["times"], surfaces=const["surfaces"])
    last_day = max(r.date for r in rows)
    if as_of is not None and len(by_round) >= 4:       # the season shows one of everything
        by_round[1][0].forfeit_by = by_round[1][0].away
        by_round[2][-1].status = "cancelled"
        by_round[3][0].forced = "tie"
        moved = by_round[-1][-1]
        moved.moved_from, moved.date = moved.date.isoformat(), moved.date + dt.timedelta(days=5)
    played_rows = [r for r in rows if r.status != "cancelled" and (as_of is None or r.date <= as_of)]
    ordinary = [r for r in played_rows if r.forfeit_by is None]
    if as_of is not None and ordinary:
        max(ordinary, key=lambda r: (r.date, r.time, r.game_id)).draft = True     # the sheet not typed in yet
    rows.extend(playoff_rows(sport, last_day, len(ids), times=const["times"], surfaces=const["surfaces"]))

    files: dict[str, str] = {}
    wins = {i: 0.0 for i in ids}
    playoff_winner: dict[str, str] = {}
    seeds: list[str] | None = None                      # the regular-season order, fixed when the playoffs start
    for row in sorted(rows, key=lambda r: (r.date, r.time, r.game_id)):
        if row.type == "playoff":
            if seeds is None and (as_of is None or row.date <= as_of):
                seeds = seed_order(ids, wins)
            _resolve_playoff_teams(row, seeds, playoff_winner, len(ids))
        if row.status == "cancelled" or (as_of is not None and row.date > as_of):
            continue
        if row.type == "playoff" and row.home not in team_map:
            continue
        name = f"{row.game_id}.yml"
        envelope = {"game_id": row.game_id, "status": "final", "home": row.home, "away": row.away,
                    "checked_by": rng.choice(CHECKERS)}
        if row.forfeit_by:
            envelope["forfeit"] = row.forfeit_by
            wins[row.away if row.forfeit_by == row.home else row.home] += 1
            files[f"games/{name}"] = dump_yaml(envelope)
            continue
        folder = "drafts" if row.draft else "games"
        ctx = SportContext(sport=sport.spec, options=rules, teams=team_map, players=player_map,
                           sides={"home": row.home, "away": row.away}, game_type=row.type, folder=folder)
        outcome = pick_outcome(rng, row.type, rules, standings, row.forced)
        game = SampleGame(row.game_id, pick_players(rng, roster, spares, row.home, row.away), outcome)
        sheet = call_sport("sheet", sample.sheet, rng, game, ctx)
        problems = [p for p in call_sport("check", rules_mod.check, sheet, ctx)
                    if not (row.draft and p.level == "warning")]
        if problems:
            raise SampleError(f"the sample sheet for {row.game_id} in {season['id']} fails the {sport.id} rules: "
                              + "; ".join(f"{p.at}: {p.message}" for p in problems))
        reading = call_sport("read", rules_mod.read, sheet, ctx)
        call_sport("present", rules_mod.present, reading, ctx)
        if collect is not None:
            collect.append((sheet, ctx, game))
        final = reading.score.final
        if final["home"] != final["away"]:
            winner = row.home if final["home"] > final["away"] else row.away
            if row.type == "playoff":
                playoff_winner[row.slot] = winner      # playoff wins never move the seeds
            else:
                wins[winner] += 1
        elif row.type == "regular":
            wins[row.home] += 0.5
            wins[row.away] += 0.5
        if row.draft:
            envelope["status"] = "draft"
            envelope.pop("checked_by")
            envelope["review"] = [Flow({"at": reading.score.final_at["home"],
                                        "note": "Check this score against the photo of the sheet."})]
        elif rng.random() < 0.5:
            envelope["scorekeeper"] = rng.choice(CHECKERS)
        if not row.draft and rng.random() < 0.12:
            envelope["notes"] = [Flow({"text": rng.choice(const["notes"])})]
        envelope["sheet"] = flowify(sheet)
        files[f"{folder}/{name}"] = dump_yaml(envelope)

    files["teams.yml"] = dump_yaml([Flow({"id": t.id, "name": t.name, "code": t.code}) for t in teams])
    files["players.yml"] = dump_yaml(player_rows(players))
    files["schedule.csv"] = schedule_csv(sorted(rows, key=lambda r: (r.date, r.time, r.game_id)))
    return files


def seed_order(ids: list[str], wins: dict[str, float]) -> list[str]:
    """The teams best first by regular-season wins (ties by roster order): a proxy for the real standings."""
    return sorted(ids, key=lambda i: (-wins[i], ids.index(i)))


def _resolve_playoff_teams(row: Row, seeds: list[str] | None, winners: dict[str, str], n_teams: int) -> None:
    """Fill a playoff row's teams once they are known: the semifinals and a two-team final from `seeds` (fixed
    before the first playoff game, so a semifinal win cannot move a team into the other semifinal), the final
    from the two semifinal winners. `seeds` is None while the playoffs are still to come."""
    if row.slot == "final" and n_teams >= 4:
        if "sf1" in winners and "sf2" in winners:
            row.home, row.away = winners["sf1"], winners["sf2"]
        return
    if seeds is None:
        return
    if row.slot == "sf1":
        row.home, row.away = seeds[0], seeds[3]
    elif row.slot == "sf2":
        row.home, row.away = seeds[1], seeds[2]
    else:
        row.home, row.away = seeds[0], seeds[1]


def schedule_csv(rows: list[Row]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(row.csv())
    return out.getvalue()


# ------------------------------------------------------------------ the whole data folder

def sample_seasons(root: Path) -> list[dict]:
    """The `sample: true` seasons of data/seasons.yml."""
    seasons, problems = read_yaml(root / "data" / "seasons.yml", "data/seasons.yml")
    if problems or not isinstance(seasons, list):
        raise SampleError("data/seasons.yml could not be read: " + "; ".join(p.message for p in problems))
    return [s for s in seasons if isinstance(s, dict) and s.get("sample")]


def generate_all(root: Path = ROOT, *, seed: str = SEED) -> dict[str, dict[str, str]]:
    """{season id: {path: text}} for every sample season, from league.yml's sport."""
    league, problems = load_league(root / "league.yml", sports_root=root / "sports", root=root)
    if league is None:
        raise SampleError("league.yml has problems: " + "; ".join(f"{p.at}: {p.message}" for p in problems))
    sport, problems = load_sport(league.sport, root / "sports", root=root, with_sample=True)
    if sport is None:
        raise SampleError("the sport could not be loaded: " + "; ".join(f"{p.file}: {p.message}" for p in problems))
    out = {}
    for index, season in enumerate(sample_seasons(root)):
        settings, problems = effective_settings(league, season.get("overrides"), at=f"{index}.overrides")
        if problems:
            raise SampleError("overrides in data/seasons.yml: " + "; ".join(f"{p.at}: {p.message}" for p in problems))
        out[season["id"]] = generate_season(sport, season, rules=settings.rules, standings=settings.standings, seed=seed)
    return out


def files_on_disk(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(folder.rglob("*")) if p.is_file()} if folder.is_dir() else {}


def write_all(root: Path, made: dict[str, dict[str, str]]) -> None:
    for season_id, files in made.items():
        folder = root / "data" / season_id
        if folder.exists():
            shutil.rmtree(folder)
        for rel, text in files.items():
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")


def differences(root: Path, made: dict[str, dict[str, str]]) -> list[str]:
    found = []
    for season_id, files in made.items():
        disk = files_on_disk(root / "data" / season_id)
        for rel in sorted(set(files) | set(disk)):
            if rel not in disk:
                found.append(f"data/{season_id}/{rel}: missing")
            elif rel not in files:
                found.append(f"data/{season_id}/{rel}: not written by make_sample.py")
            elif disk[rel] != files[rel]:
                found.append(f"data/{season_id}/{rel}: differs")
    return found


def run_loader(root: Path) -> list[str]:
    """Every problem (errors and warnings) the loader finds in the data folder under `root`, printed as
    "file: at: message"."""
    from scripts.core.loader import load_data
    league, problems = load_league(root / "league.yml", sports_root=root / "sports", root=root)
    if league is None:
        return [f"{p.file}: {p.at}: {p.message}" for p in problems]
    sport, problems = load_sport(league.sport, root / "sports", root=root, with_sample=True)
    if sport is None:
        return [f"{p.file}: {p.at}: {p.message}" for p in problems]
    data = load_data(root, league, sport, today=dt.date(2026, 10, 15))
    return [f"{p.file}: {p.at}: {p.message}" for p in data.problems]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the made-up sample seasons (data/sample-*/).")
    parser.add_argument("--check", action="store_true", help="change nothing; fail if the files on disk differ")
    parser.add_argument("--root", type=Path, default=ROOT, help="the repository root (default: this one)")
    parser.add_argument("--no-loader", action="store_true", help="skip running the loader on what was written")
    args = parser.parse_args(argv)
    try:
        made = generate_all(args.root)
        if not made:
            print("No season in data/seasons.yml has 'sample: true'; nothing to write.")
            return 0
        if args.check:
            found = differences(args.root, made)
            for line in found:
                print(line)
            print("The sample data is up to date." if not found else "Run: python scripts/make_sample.py")
            return 1 if found else 0
        write_all(args.root, made)
        print(f"Wrote {', '.join('data/' + s + '/' for s in made)} ({sum(len(f) for f in made.values())} files).")
        if not args.no_loader:
            problems = run_loader(args.root)
            if problems:
                print("The loader found problems in what was written:", *problems, sep="\n  ")
                return 1
            else:
                print("The loader found no problems.")
        return 0
    except SampleError as exc:
        print(f"make_sample.py: {exc}", file=sys.stderr)
        return 1
    except InternalError as exc:
        print(f"make_sample.py: internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
