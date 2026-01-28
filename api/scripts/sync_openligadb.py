import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
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


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} {msg}")

def get_field(obj, *names):
    if not isinstance(obj, dict):
        return None
    for name in names:
        if name in obj:
            return obj.get(name)
        # case-insensitive fallback
        for key in obj.keys():
            if key.lower() == name.lower():
                return obj.get(key)
    return None


def fetch_json(path):
    url = f"{BASE_URL}{path}"
    req = Request(url, headers={"User-Agent": "MatchVoteSync/1.0"})
    with urlopen(req, timeout=30) as resp:
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
        if "/" in season_value:
            tokens.append(season_value.split("/")[0])

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


def insert_match(conn, payload, include_matchday):
    if include_matchday:
        sql = text("""
            insert into referee_ratings.matches
              (league, season, match_date, team_home, team_away, matchday_number, matchday_name, matchday_name_en)
            select
              :league, :season, :match_date, :team_home, :team_away, :matchday_number, :matchday_name, :matchday_name_en
            where not exists (
                select 1 from referee_ratings.matches
                where league = :league
                  and season = :season
                  and match_date = :match_date
                  and team_home = :team_home
                  and team_away = :team_away
            )
        """)
    else:
        sql = text("""
            insert into referee_ratings.matches (league, season, match_date, team_home, team_away)
            select :league, :season, :match_date, :team_home, :team_away
            where not exists (
                select 1 from referee_ratings.matches
                where league = :league
                  and season = :season
                  and match_date = :match_date
                  and team_home = :team_home
                  and team_away = :team_away
            )
        """)
    result = conn.execute(sql, payload)
    return 1 if result.rowcount else 0


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


def season_exists(conn, league, season_value):
    sql = text("""
        select 1 from referee_ratings.matches
        where league = :league and season = :season
        limit 1
    """)
    row = conn.execute(sql, {"league": league, "season": season_value}).first()
    return row is not None


def sync_league(league, season_override=None, force=False):
    season = season_override or latest_season_for(league)
    if not season:
        log(f"[{league}] No season found.")
        return 0

    matches = fetch_matches(league, season)
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        season_str = str(season)
        if season_exists(conn, league, season_str) and not force:
            log(f"[{league}] season={season_str} already present; skipping (use --force to resync).")
            return 0

        include_matchday = (
            column_exists(conn, "referee_ratings", "matches", "matchday_number")
            and column_exists(conn, "referee_ratings", "matches", "matchday_name")
            and column_exists(conn, "referee_ratings", "matches", "matchday_name_en")
        )
        for item in matches:
            match_date = parse_match_datetime(item)
            team_home = extract_team_name(get_field(item, "team1", "Team1"))
            team_away = extract_team_name(get_field(item, "team2", "Team2"))
            season_value = get_field(item, "LeagueSeason", "leagueSeason") or season
            season_value = str(season_value)
            matchday_number, matchday_name, matchday_name_en = extract_matchday(item)

            if not match_date or not team_home or not team_away:
                skipped += 1
                continue

            payload = {
                "league": league,
                "season": season_value,
                "match_date": match_date,
                "team_home": team_home,
                "team_away": team_away,
                "matchday_number": matchday_number,
                "matchday_name": matchday_name,
                "matchday_name_en": matchday_name_en,
            }
            inserted += insert_match(conn, payload, include_matchday)

    log(f"[{league}] season={season} matches={len(matches)} inserted={inserted} skipped={skipped}")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Sync matches from OpenLigaDB into referee_ratings.matches")
    parser.add_argument("--league", choices=LEAGUES, help="Limit sync to a single league")
    parser.add_argument("--season", help="Override season (applies to all selected leagues)")
    parser.add_argument("--force", action="store_true", help="Sync even if season already exists")
    args = parser.parse_args()

    leagues = (args.league,) if args.league else LEAGUES
    total = 0
    for league in leagues:
        total += sync_league(league, season_override=args.season, force=args.force)

    log(f"Total inserted: {total}")


if __name__ == "__main__":
    main()
