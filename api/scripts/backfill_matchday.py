import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import text

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import engine

BASE_URL = os.getenv("OPENLIGADB_BASE_URL", "https://api.openligadb.de").rstrip("/")
LEAGUES = ("BL1", "BL2")
REQUEST_TIMEOUT = 30


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} {msg}")


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


def fetch_json(path):
    url = f"{BASE_URL}{path}"
    req = Request(url, headers={"User-Agent": "MatchVoteBackfill/1.0"})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def season_sort_key(value):
    if not value:
        return 0
    match = re.search(r"(19|20)\d{2}", value)
    return int(match.group(0)) if match else 0


def latest_season_for(league_shortcut):
    leagues = fetch_json("/getavailableleagues")
    target = league_shortcut.lower()
    candidates = [
        l for l in leagues
        if str(get_field(l, "LeagueShortcut", "leagueShortcut")).lower() == target
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda l: season_sort_key(get_field(l, "LeagueSeason", "leagueSeason")), reverse=True)
    return get_field(candidates[0], "LeagueSeason", "leagueSeason")


def fetch_matches(league_shortcut, season_value):
    league_lower = league_shortcut.lower()
    tokens = []
    if season_value:
        tokens.append(season_value)
        if "/" in str(season_value):
            tokens.append(str(season_value).split("/")[0])

    last_error = None
    for token in tokens:
        try:
            encoded = quote(str(token), safe="")
            return fetch_json(f"/getmatchdata/{league_lower}/{encoded}")
        except (HTTPError, URLError) as exc:
            last_error = exc

    if last_error:
        raise last_error
    return []


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


def normalize_team(name):
    if not name:
        return None
    normalized = " ".join(str(name).strip().split())
    return normalized.lower()


def extract_matchday(item):
    group = get_field(item, "group", "Group")
    matchday_number = None
    matchday_name = None
    matchday_name_en = None
    if isinstance(group, dict):
        matchday_name = get_field(group, "groupName", "GroupName", "name", "Name")
        matchday_number = get_field(
            group,
            "groupOrderID",
            "GroupOrderID",
            "groupOrderId",
            "GroupOrderId",
            "groupOrder",
            "GroupOrder",
            "groupID",
            "GroupID",
        )
    if matchday_name is None:
        matchday_name = get_field(item, "groupName", "GroupName")
    if matchday_number is None:
        matchday_number = get_field(item, "groupOrderID", "GroupOrderID", "groupOrderId", "GroupOrderId")
    try:
        matchday_number = int(matchday_number) if matchday_number is not None else None
    except (TypeError, ValueError):
        matchday_number = None
    if matchday_number is not None:
        matchday_name_en = f"Matchday {matchday_number}"
    return matchday_number, matchday_name, matchday_name_en


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


def update_matchday(conn, match_id, matchday_number, matchday_name, matchday_name_en):
    sql = text("""
        update referee_ratings.matches
        set
          matchday_number = :matchday_number,
          matchday_name = :matchday_name,
          matchday_name_en = :matchday_name_en
        where match_id = cast(:match_id as uuid)
          and (
            matchday_number is distinct from :matchday_number
            or matchday_name is distinct from :matchday_name
            or matchday_name_en is distinct from :matchday_name_en
          )
    """)
    result = conn.execute(sql, {
        "match_id": str(match_id),
        "matchday_number": matchday_number,
        "matchday_name": matchday_name,
        "matchday_name_en": matchday_name_en,
    })
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Backfill matchday fields in referee_ratings.matches")
    parser.add_argument("--league", choices=LEAGUES, help="Limit sync to a single league")
    parser.add_argument("--season", help="Override season (applies to all selected leagues)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    leagues = (args.league,) if args.league else LEAGUES
    total_updated = 0
    total_missing = 0

    with engine.begin() as conn:
        if not column_exists(conn, "referee_ratings", "matches", "matchday_number"):
            log("Missing column referee_ratings.matches.matchday_number")
            raise SystemExit(1)
        if not column_exists(conn, "referee_ratings", "matches", "matchday_name"):
            log("Missing column referee_ratings.matches.matchday_name")
            raise SystemExit(1)
        if not column_exists(conn, "referee_ratings", "matches", "matchday_name_en"):
            log("Missing column referee_ratings.matches.matchday_name_en")
            raise SystemExit(1)

    for league in leagues:
        season = args.season or latest_season_for(league)
        if not season:
            log(f"[{league}] No season found.")
            continue

        matches = fetch_matches(league, season)
        updated = 0
        skipped = 0
        missing = 0

        with engine.begin() as conn:
            for item in matches:
                kickoff = parse_match_datetime(item)
                team_home = extract_team_name(get_field(item, "team1", "Team1"))
                team_away = extract_team_name(get_field(item, "team2", "Team2"))
                match_id = find_match_id(conn, league, kickoff, team_home, team_away)
                if not match_id:
                    missing += 1
                    continue
                matchday_number, matchday_name, matchday_name_en = extract_matchday(item)
                if matchday_number is None and not matchday_name and not matchday_name_en:
                    skipped += 1
                    continue
                if args.dry_run:
                    updated += 1
                    continue
                updated += update_matchday(conn, match_id, matchday_number, matchday_name, matchday_name_en)

        log(f"[{league}] season={season} matches={len(matches)} updated={updated} skipped={skipped} missing={missing}")
        total_updated += updated
        total_missing += missing

    log(f"Total updated: {total_updated} missing matches: {total_missing}")


if __name__ == "__main__":
    main()
