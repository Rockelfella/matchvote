from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import text

from app.db import engine


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _extract_fixtures(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "fixtures", "schedule"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def _extract_team_ids(fixture: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    home_id = _get_int(fixture.get("home_team_id")) or _get_int(fixture.get("home_id"))
    away_id = _get_int(fixture.get("away_team_id")) or _get_int(fixture.get("away_id"))

    participants = fixture.get("participants")
    if isinstance(participants, dict):
        participants = participants.get("data")
    if isinstance(participants, list):
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            team_id = _get_int(participant.get("id"))
            meta = participant.get("meta") if isinstance(participant.get("meta"), dict) else {}
            location = meta.get("location")
            if location == "home" and home_id is None:
                home_id = team_id
            elif location == "away" and away_id is None:
                away_id = team_id
    return home_id, away_id


def _extract_starts_at(fixture: Dict[str, Any]) -> Optional[datetime]:
    return (
        _parse_datetime(fixture.get("starting_at"))
        or _parse_datetime(fixture.get("starts_at"))
        or _parse_datetime(fixture.get("kickoff"))
        or _parse_datetime(fixture.get("starting_at_timestamp"))
    )


def _extract_status(fixture: Dict[str, Any]) -> Optional[str]:
    state_id = _get_int(fixture.get("state_id"))
    if state_id is not None:
        return str(state_id)
    status = fixture.get("status")
    if isinstance(status, dict):
        raw = status.get("short") or status.get("name")
        return str(raw).strip() if raw is not None else None
    if status is None:
        return None
    return str(status).strip()


def insert_schedule_raw(
    payload: Any,
    request_params: Optional[Dict[str, Any]],
    fetched_at: Optional[datetime] = None,
) -> int:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    sql = text("""
        insert into referee_ratings.sportmonks_schedule_raw
          (fetched_at, request_params, payload)
        values
          (:fetched_at, :request_params::jsonb, :payload::jsonb)
        returning id
    """)
    params = {
        "fetched_at": fetched_at,
        "request_params": json.dumps(request_params or {}),
        "payload": json.dumps(payload),
    }
    with engine.begin() as conn:
        row = conn.execute(sql, params).first()
        return int(row[0]) if row else 0


def upsert_schedule_fixtures(
    payload: Any,
    fetched_at: Optional[datetime] = None,
) -> Dict[str, int]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    fixtures = _extract_fixtures(payload)
    if not fixtures:
        return {"processed": 0, "inserted": 0, "updated": 0}

    sql = text("""
        insert into referee_ratings.sportmonks_schedule_fixture (
            fixture_id,
            starts_at,
            home_id,
            away_id,
            league_id,
            season_id,
            status,
            venue_id,
            score_home,
            score_away,
            updated_at
        ) values (
            :fixture_id,
            :starts_at,
            :home_id,
            :away_id,
            :league_id,
            :season_id,
            :status,
            :venue_id,
            :score_home,
            :score_away,
            :updated_at
        )
        on conflict (fixture_id) do update set
            starts_at = excluded.starts_at,
            home_id = excluded.home_id,
            away_id = excluded.away_id,
            league_id = excluded.league_id,
            season_id = excluded.season_id,
            status = excluded.status,
            venue_id = excluded.venue_id,
            score_home = excluded.score_home,
            score_away = excluded.score_away,
            updated_at = excluded.updated_at
        returning (xmax = 0) as inserted
    """)

    inserted = 0
    updated = 0
    with engine.begin() as conn:
        for fixture in fixtures:
            fixture_id = _get_int(fixture.get("id"))
            if fixture_id is None:
                continue
            home_id, away_id = _extract_team_ids(fixture)
            venue_id = _get_int(fixture.get("venue_id"))
            if venue_id is None and isinstance(fixture.get("venue"), dict):
                venue_id = _get_int(fixture["venue"].get("id"))

            payload_row = {
                "fixture_id": fixture_id,
                "starts_at": _extract_starts_at(fixture),
                "home_id": home_id,
                "away_id": away_id,
                "league_id": _get_int(fixture.get("league_id")),
                "season_id": _get_int(fixture.get("season_id")),
                "status": _extract_status(fixture),
                "venue_id": venue_id,
                "score_home": None,
                "score_away": None,
                "updated_at": fetched_at,
            }
            row = conn.execute(sql, payload_row).mappings().first()
            if row and row.get("inserted"):
                inserted += 1
            else:
                updated += 1

    return {"processed": len(fixtures), "inserted": inserted, "updated": updated}


def list_schedule_fixtures(
    limit: int,
    offset: int,
    league_ids: Optional[Sequence[int]] = None,
    season_ids: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    clauses = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if league_ids:
        clauses.append("league_id = any(:league_ids)")
        params["league_ids"] = list(league_ids)
    if season_ids:
        clauses.append("season_id = any(:season_ids)")
        params["season_ids"] = list(season_ids)

    sql = """
        select
          fixture_id,
          starts_at,
          home_id,
          away_id,
          league_id,
          season_id
        from referee_ratings.sportmonks_schedule_fixture
    """
    if clauses:
        sql += " where " + " and ".join(clauses)
    sql += " order by starts_at desc nulls last limit :limit offset :offset"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(row) for row in rows]
