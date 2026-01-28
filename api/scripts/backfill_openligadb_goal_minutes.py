import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests
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

REQUEST_TIMEOUT = (5, 20)


def log(message):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} {message}")


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
    normalized = " ".join(str(name).strip().split())
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
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "MatchVoteGoalBackfill/1.0"})
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
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "MatchVoteGoalBackfill/1.0"})
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise last_error
    return []


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


def build_descriptions(goal, minute, stoppage):
    score1 = get_field(goal, "scoreTeam1", "ScoreTeam1")
    score2 = get_field(goal, "scoreTeam2", "ScoreTeam2")
    score1 = int(score1) if score1 is not None else 0
    score2 = int(score2) if score2 is not None else 0
    minute_label = f"{minute}+{stoppage}" if stoppage is not None else f"{minute}"
    description_de = f"Tor: {minute_label}' Stand {score1} - {score2}"
    description_en = f"Goal: {minute_label}' Score {score1} - {score2}"
    return description_de, description_en


def find_match_id(conn, league, kickoff, team_home, team_away):
    if not kickoff or not team_home or not team_away:
        return None
    window_start = kickoff - timedelta(hours=2)
    window_end = kickoff + timedelta(hours=2)
    sql = text("""
        select match_id
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


def find_scene_id(conn, match_id, goal_id):
    marker = f"%oldb_goal_id={goal_id}%"
    sql = text("""
        select scene_id
        from referee_ratings.scenes
        where match_id = cast(:match_id as uuid)
          and scene_type = 'GOAL'
          and (
            description like :marker
            or description_de like :marker
            or description_en like :marker
          )
        limit 1
    """)
    row = conn.execute(sql, {"match_id": str(match_id), "marker": marker}).mappings().first()
    if not row:
        return None
    return row["scene_id"]


def update_scene(conn, scene_id, minute, stoppage, description_de, description_en):
    sql = text("""
        update referee_ratings.scenes
        set
          minute = :minute,
          stoppage_time = :stoppage_time,
          description_de = :description_de,
          description_en = :description_en
        where scene_id = cast(:scene_id as uuid)
    """)
    result = conn.execute(sql, {
        "scene_id": str(scene_id),
        "minute": minute,
        "stoppage_time": stoppage,
        "description_de": description_de,
        "description_en": description_en,
    })
    return result.rowcount


def parse_leagues(raw_leagues):
    if not raw_leagues:
        return []
    tokens = re.split(r"[,\s]+", raw_leagues.strip())
    return [token.upper() for token in tokens if token]


def main():
    parser = argparse.ArgumentParser(description="Backfill OpenLigaDB goal minutes in referee_ratings.scenes")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--group", default=DEFAULT_GROUP)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.season == "":
        args.season = None
    if args.group == "":
        args.group = None

    updated_total = 0
    missing_matches = 0
    missing_scenes = 0

    leagues = parse_leagues(args.league) or list(LEAGUES)
    for league in leagues:
        log(f"Start backfill league={league} season={args.season} group={args.group} dry_run={args.dry_run}")
        matches = fetch_matches(league, args.season, args.group)
        updated = 0
        with engine.begin() as conn:
            for item in matches:
                kickoff = parse_match_datetime(item)
                team_home = extract_team_name(get_field(item, "team1", "Team1"))
                team_away = extract_team_name(get_field(item, "team2", "Team2"))
                match_id = find_match_id(conn, league.upper(), kickoff, team_home, team_away)
                if not match_id:
                    missing_matches += 1
                    continue
                goals = get_field(item, "goals", "Goals") or []
                for goal in goals:
                    goal_id = get_field(goal, "goalID", "GoalID")
                    if goal_id is None:
                        continue
                    minute, stoppage = parse_goal_minute(goal)
                    if minute is None:
                        continue
                    description_de, description_en = build_descriptions(goal, minute, stoppage)
                    scene_id = find_scene_id(conn, match_id, goal_id)
                    if not scene_id:
                        missing_scenes += 1
                        continue
                    if args.dry_run:
                        updated += 1
                        continue
                    updated += update_scene(conn, scene_id, minute, stoppage, description_de, description_en)
        updated_total += updated
        log(f"[{league}] Done updated={updated}")

    log(f"Total updated: {updated_total} missing_matches={missing_matches} missing_scenes={missing_scenes}")


if __name__ == "__main__":
    main()
