from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _extract_team_ids(fixture: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
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


def _extract_minute(fixture: Dict[str, Any]) -> Optional[int]:
    minute = _get_int(fixture.get("minute"))
    if minute is not None:
        return minute
    time_data = fixture.get("time")
    if isinstance(time_data, dict):
        for key in ("minute", "minutes", "added_time", "injury_time"):
            minute = _get_int(time_data.get(key))
            if minute is not None:
                return minute
    return None


def _extract_period(fixture: Dict[str, Any]) -> Optional[str]:
    period = fixture.get("period")
    if period is not None:
        return str(period)
    time_data = fixture.get("time")
    if isinstance(time_data, dict):
        for key in ("period", "status", "period_id"):
            value = time_data.get(key)
            if value is not None:
                return str(value)
    return None


def _extract_scores(fixture: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    candidates: List[Dict[str, Any]] = []
    scores = fixture.get("scores")
    if isinstance(scores, dict):
        scores = scores.get("data")
    if isinstance(scores, list):
        candidates = [item for item in scores if isinstance(item, dict)]

    preferred = None
    for item in candidates:
        label = str(item.get("description") or item.get("type") or "").upper()
        if label in {"CURRENT", "LIVE", "FT", "FULL_TIME", "HT"}:
            preferred = item
            break
    if preferred is None and candidates:
        preferred = candidates[0]

    if preferred:
        home = _get_int(preferred.get("home_score") or preferred.get("home"))
        away = _get_int(preferred.get("away_score") or preferred.get("away"))
        if home is not None or away is not None:
            return home, away
        score = preferred.get("score")
        if isinstance(score, str) and "-" in score:
            parts = [p.strip() for p in score.split("-", 1)]
            if len(parts) == 2:
                return _get_int(parts[0]), _get_int(parts[1])

    return None, None


def insert_inplay_raw(
    payload: Any,
    request_params: Optional[Dict[str, Any]],
    fetched_at: Optional[datetime] = None,
    fixture_id: Optional[int] = None,
) -> int:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    sql = text("""
        insert into referee_ratings.sportmonks_inplay_raw
          (fetched_at, fixture_id, request_params, payload)
        values
          (:fetched_at, :fixture_id, :request_params::jsonb, :payload::jsonb)
        returning id
    """)
    params = {
        "fetched_at": fetched_at,
        "fixture_id": fixture_id,
        "request_params": json.dumps(request_params or {}),
        "payload": json.dumps(payload),
    }
    with engine.begin() as conn:
        row = conn.execute(sql, params).first()
        return int(row[0]) if row else 0


def upsert_inplay_state(
    payload: Any,
    fetched_at: Optional[datetime] = None,
) -> Dict[str, int]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    fixtures = _extract_fixtures(payload)
    if not fixtures:
        return {"processed": 0, "inserted": 0, "updated": 0}

    sql = text("""
        insert into referee_ratings.sportmonks_inplay_state (
            fixture_id,
            updated_at,
            status,
            minute,
            period,
            score_home,
            score_away,
            starts_at,
            home_id,
            away_id,
            league_id,
            season_id
        ) values (
            :fixture_id,
            :updated_at,
            :status,
            :minute,
            :period,
            :score_home,
            :score_away,
            :starts_at,
            :home_id,
            :away_id,
            :league_id,
            :season_id
        )
        on conflict (fixture_id) do update set
            updated_at = excluded.updated_at,
            status = excluded.status,
            minute = excluded.minute,
            period = excluded.period,
            score_home = excluded.score_home,
            score_away = excluded.score_away,
            starts_at = excluded.starts_at,
            home_id = excluded.home_id,
            away_id = excluded.away_id,
            league_id = excluded.league_id,
            season_id = excluded.season_id
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
            score_home, score_away = _extract_scores(fixture)
            payload_row = {
                "fixture_id": fixture_id,
                "updated_at": fetched_at,
                "status": _extract_status(fixture),
                "minute": _extract_minute(fixture),
                "period": _extract_period(fixture),
                "score_home": score_home,
                "score_away": score_away,
                "starts_at": _extract_starts_at(fixture),
                "home_id": home_id,
                "away_id": away_id,
                "league_id": _get_int(fixture.get("league_id")),
                "season_id": _get_int(fixture.get("season_id")),
            }
            row = conn.execute(sql, payload_row).mappings().first()
            if row and row.get("inserted"):
                inserted += 1
            else:
                updated += 1

    return {"processed": len(fixtures), "inserted": inserted, "updated": updated}


def get_inplay_snapshot() -> Dict[str, Any]:
    sql = text("""
        select
          (select max(fetched_at) from referee_ratings.sportmonks_inplay_raw) as last_fetched_at,
          (select count(*) from referee_ratings.sportmonks_inplay_state) as fixtures
    """)
    with engine.connect() as conn:
        row = conn.execute(sql).mappings().first()
    return dict(row) if row else {"last_fetched_at": None, "fixtures": 0}
