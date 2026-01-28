import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from urllib.parse import quote
from sqlalchemy import text

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import engine

BASE_URL = os.getenv("OPENLIGADB_BASE_URL", "https://api.openligadb.de").rstrip("/")
LEAGUES = ("BL1", "BL2")
DEFAULT_LEAGUE = os.getenv("OPENLIGADB_LEAGUE", "bl1,bl2")
DEFAULT_SEASON = os.getenv("OPENLIGADB_SEASON")
DEFAULT_GROUP = os.getenv("OPENLIGADB_GROUP")
IMPORT_RELEASE_IMMEDIATELY = os.getenv("IMPORT_RELEASE_IMMEDIATELY", "true").lower() in ("1", "true", "yes", "y")
IMPORT_LOG = os.getenv("IMPORT_LOG")
IMPORT_CREATED_BY = os.getenv("IMPORT_CREATED_BY")

REQUEST_TIMEOUT = (5, 20)


def log(message):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} {message}"
    print(line)
    if IMPORT_LOG:
        with open(IMPORT_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def get_field(obj, *names):
    if not isinstance(obj, dict):
        return None
    for name in names:
        if name in obj:
            return obj.get(name)
        for key in obj.keys():
            if key.lower() == name.lower():
                return obj.get(key)
    return None


def normalize_team(name):
    if not name:
        return None
    normalized = " ".join(name.strip().split())
    return normalized.lower()


def parse_match_datetime(item):
    for key in ("matchDateTimeUTC", "matchDateTime", "MatchDateTimeUTC", "MatchDateTime"):
        value = get_field(item, key)
        if not value:
            continue
        try:
            if value.endswith("Z"):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def extract_team_name(team_obj):
    if not isinstance(team_obj, dict):
        return None
    return get_field(team_obj, "teamName", "shortName", "TeamName", "TeamNameShort")


def build_match_url(league, season, group):
    league = league.lower()
    if season and group:
        return f"{BASE_URL}/getmatchdata/{league}/{quote(str(season), safe='')}/{quote(str(group), safe='')}"
    if season:
        return f"{BASE_URL}/getmatchdata/{league}/{quote(str(season), safe='')}"
    return f"{BASE_URL}/getmatchdata/{league}"


def fetch_matches(league, season, group):
    if group:
        url = build_match_url(league, season, group)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "MatchVoteGoalImport/1.0"})
        resp.raise_for_status()
        return resp.json()

    tokens = []
    if season:
        tokens.append(season)
        if "/" in str(season):
            tokens.append(str(season).split("/")[0])

    last_error = None
    for token in tokens:
        try:
            url = build_match_url(league, token, None)
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "MatchVoteGoalImport/1.0"})
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise last_error
    return []


def column_exists(conn, schema, table, column):
    row = conn.execute(text("""
        select 1
        from information_schema.columns
        where table_schema = :schema
          and table_name = :table
          and column_name = :column
        limit 1
    """), {"schema": schema, "table": table, "column": column}).first()
    return bool(row)


def find_match_id(conn, league, kickoff, team_home, team_away):
    if not kickoff or not team_home or not team_away:
        return None
    window_start = kickoff - timedelta(hours=2)
    window_end = kickoff + timedelta(hours=2)
    sql = text("""
        select match_id, match_date
        from referee_ratings.matches
        where league = :league
          and match_date between :start_time and :end_time
          and lower(trim(team_home)) = :team_home
          and lower(trim(team_away)) = :team_away
        order by abs(extract(epoch from (match_date - :kickoff))) asc
        limit 1
    """)
    row = conn.execute(sql, {
        "league": league,
        "start_time": window_start,
        "end_time": window_end,
        "team_home": normalize_team(team_home),
        "team_away": normalize_team(team_away),
        "kickoff": kickoff,
    }).mappings().first()
    if not row:
        return None
    return row["match_id"]


def goal_exists(conn, match_id, goal_id, description_column):
    sql = text("""
        select 1
        from referee_ratings.scenes
        where match_id = cast(:match_id as uuid)
          and scene_type = 'GOAL'
          and {description_column} like :marker
        limit 1
    """.format(description_column=description_column))
    marker = f"%oldb_goal_id={goal_id}%"
    row = conn.execute(sql, {"match_id": str(match_id), "marker": marker}).first()
    return row is not None


def parse_goal_minute(goal):
    raw = get_field(goal, "matchMinute", "MatchMinute", "minute", "Minute")
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return int(raw), None
    text = str(raw).strip()
    if not text:
        return None, None
    text = text.replace("'", "").replace("’", "").replace("`", "")
    plus_match = re.search(r"(\d{1,3})\s*\+\s*(\d{1,2})", text)
    if plus_match:
        return int(plus_match.group(1)), int(plus_match.group(2))
    num_match = re.search(r"(\d{1,3})", text)
    if num_match:
        return int(num_match.group(1)), None
    return None, None


def build_descriptions(goal):
    minute, stoppage = parse_goal_minute(goal)
    minute = minute if minute is not None else 0
    score1 = get_field(goal, "scoreTeam1", "ScoreTeam1")
    score2 = get_field(goal, "scoreTeam2", "ScoreTeam2")
    score1 = int(score1) if score1 is not None else 0
    score2 = int(score2) if score2 is not None else 0
    goal_id = get_field(goal, "goalID", "GoalID")
    marker = f"oldb_goal_id={goal_id}"
    minute_label = f"{minute}+{stoppage}" if stoppage is not None else f"{minute}"
    description_de = f"Tor: {minute_label}' Stand {score1} - {score2}"
    description_en = f"Goal: {minute_label}' Score {score1} - {score2}"
    return description_de, description_en, marker, minute, stoppage


def insert_goal_scene(conn, match_id, goal, dry_run, description_column, include_legacy):
    goal_id = get_field(goal, "goalID", "GoalID")
    if goal_id is None:
        return "skipped_missing_id"

    if goal_exists(conn, match_id, goal_id, description_column):
        return "skipped_exists"

    description_de, description_en, marker, minute, stoppage = build_descriptions(goal)
    minute = minute if minute is not None else 0

    if dry_run:
        log(f"[dry-run] Would insert GOAL scene match_id={match_id} goal_id={goal_id}")
        return "dry_run"

    if include_legacy:
        sql = text("""
            insert into referee_ratings.scenes
              (match_id, minute, stoppage_time, scene_type, description, description_de, description_en, is_released, release_time, created_by)
            values
              (:match_id, :minute, :stoppage_time, 'GOAL', :description, :description_de, :description_en, :is_released, :release_time, :created_by)
        """)
    else:
        sql = text("""
            insert into referee_ratings.scenes
              (match_id, minute, stoppage_time, scene_type, description_de, description_en, is_released, release_time, created_by)
            values
              (:match_id, :minute, :stoppage_time, 'GOAL', :description_de, :description_en, :is_released, :release_time, :created_by)
        """)

    params = {
        "match_id": str(match_id),
        "minute": minute,
        "stoppage_time": stoppage,
        "description": marker,
        "description_de": description_de,
        "description_en": description_en,
        "is_released": IMPORT_RELEASE_IMMEDIATELY,
        "release_time": datetime.now(timezone.utc) if IMPORT_RELEASE_IMMEDIATELY else None,
        "created_by": IMPORT_CREATED_BY,
    }
    conn.execute(sql, params)
    return "inserted"


def import_goals(league, season, group, dry_run):
    matches = fetch_matches(league, season, group)
    checked_matches = 0
    goals_found = 0
    inserted = 0
    skipped_exists = 0
    skipped_missing_id = 0
    skipped_no_match = 0
    dry_run_count = 0

    with engine.begin() as conn:
        include_legacy = column_exists(conn, "referee_ratings", "scenes", "description")
        description_column = "description" if include_legacy else "description_de"
        for item in matches:
            checked_matches += 1
            kickoff = parse_match_datetime(item)
            team_home = extract_team_name(get_field(item, "team1", "Team1"))
            team_away = extract_team_name(get_field(item, "team2", "Team2"))
            match_id = find_match_id(conn, league.upper(), kickoff, team_home, team_away)

            if not match_id:
                log(f"[skip] match not found league={league} kickoff={kickoff} home={team_home} away={team_away}")
                skipped_no_match += 1
                continue

            goals = get_field(item, "goals", "Goals") or []
            for goal in goals:
                goals_found += 1
                result = insert_goal_scene(conn, match_id, goal, dry_run, description_column, include_legacy)
                if result == "inserted":
                    inserted += 1
                elif result == "skipped_exists":
                    skipped_exists += 1
                elif result == "skipped_missing_id":
                    skipped_missing_id += 1
                elif result == "dry_run":
                    dry_run_count += 1

    return {
        "matches": checked_matches,
        "goals": goals_found,
        "inserted": inserted,
        "skipped_exists": skipped_exists,
        "skipped_missing_id": skipped_missing_id,
        "skipped_no_match": skipped_no_match,
        "dry_run": dry_run_count,
    }


def parse_leagues(raw_leagues):
    if not raw_leagues:
        return []
    tokens = re.split(r"[,\s]+", raw_leagues.strip())
    return [token.upper() for token in tokens if token]


def main():
    parser = argparse.ArgumentParser(description="Import OpenLigaDB goals into referee_ratings.scenes")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--group", default=DEFAULT_GROUP)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.season == "":
        args.season = None
    if args.group == "":
        args.group = None

    try:
        leagues = parse_leagues(args.league) or list(LEAGUES)
        for league in leagues:
            log(f"Start import league={league} season={args.season} group={args.group} dry_run={args.dry_run}")
            stats = import_goals(league, args.season, args.group, args.dry_run)
            log(
                f"[{league}] Done "
                f"matches={stats['matches']} goals={stats['goals']} inserted={stats['inserted']} "
                f"skipped_exists={stats['skipped_exists']} skipped_missing_id={stats['skipped_missing_id']} "
                f"skipped_no_match={stats['skipped_no_match']} dry_run={stats['dry_run']}"
            )
    except requests.RequestException as exc:
        log(f"ERROR OpenLigaDB request failed: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
