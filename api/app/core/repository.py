from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import text

from app.db import engine
from app.core.sportmonks.mapper import map_fixture_to_match


REQUIRED_COLUMNS = {
    "external_provider",
    "external_match_id",
    "league",
    "season",
    "match_date",
    "team_home",
    "team_away",
}

OPTIONAL_COLUMNS = {
    "matchday_number",
    "matchday_name",
    "matchday_name_en",
    "status",
    "last_polled_at",
    "last_event_id",
}


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :column
            limit 1
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).first()
    return bool(row)


def _available_columns(conn) -> set[str]:
    columns = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
    return {col for col in columns if _column_exists(conn, "referee_ratings", "matches", col)}


def _build_upsert_sql(columns: Iterable[str]) -> str:
    cols = ", ".join(columns)
    params = ", ".join(f":{c}" for c in columns)
    update_cols = [c for c in columns if c not in {"external_provider", "external_match_id"}]
    update = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    return f"""
        insert into referee_ratings.matches ({cols})
        values ({params})
        on conflict (external_provider, external_match_id)
        do update set {update}
    """


def _coerce_str(value: Any) -> Any:
    if value is None:
        return None
    return str(value)


def upsert_matches(matches: Iterable[Dict[str, Any]]) -> int:
    matches = list(matches)
    if not matches:
        return 0

    inserted = 0
    with engine.begin() as conn:
        columns = _available_columns(conn)
        missing = REQUIRED_COLUMNS - columns
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise RuntimeError(
                f"Missing required columns in referee_ratings.matches: {missing_list}"
            )

        columns = [col for col in columns if col in REQUIRED_COLUMNS | OPTIONAL_COLUMNS]
        sql = text(_build_upsert_sql(columns))

        for match in matches:
            if match.get("external_match_id") is None:
                raise RuntimeError("external_match_id is required for SportMonks matches")
            payload = {
                "external_provider": "sportmonks",
                "external_match_id": _coerce_str(match.get("external_match_id")),
                "league": _coerce_str(match.get("league_id")),
                "season": _coerce_str(match.get("season_id")),
                "match_date": match.get("kickoff"),
                "team_home": _coerce_str(match.get("home_team_name") or match.get("home_team_id")),
                "team_away": _coerce_str(match.get("away_team_name") or match.get("away_team_id")),
                "matchday_number": match.get("matchday_number"),
                "matchday_name": match.get("matchday_name"),
                "matchday_name_en": match.get("matchday_name_en"),
                "status": match.get("status"),
            }
            # Remove keys not in available columns
            payload = {k: v for k, v in payload.items() if k in columns}
            if any(payload.get(k) is None for k in REQUIRED_COLUMNS):
                raise RuntimeError("Missing required fields for SportMonks match upsert")
            result = conn.execute(sql, payload)
            if result.rowcount:
                inserted += 1

    return inserted


def upsert_match_from_sportmonks_fixture(fixture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    match = map_fixture_to_match(fixture)
    if match is None:
        return None

    with engine.begin() as conn:
        columns = _available_columns(conn)
        missing = REQUIRED_COLUMNS - columns
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise RuntimeError(
                f"Missing required columns in referee_ratings.matches: {missing_list}"
            )

        columns = [col for col in columns if col in REQUIRED_COLUMNS | OPTIONAL_COLUMNS]
        sql = text(_build_upsert_sql(columns))
        payload = {
            "external_provider": "sportmonks",
            "external_match_id": _coerce_str(match.get("external_match_id")),
            "league": _coerce_str(match.get("league_id")),
            "season": _coerce_str(match.get("season_id")),
            "match_date": match.get("kickoff"),
            "team_home": _coerce_str(match.get("home_team_name") or match.get("home_team_id")),
            "team_away": _coerce_str(match.get("away_team_name") or match.get("away_team_id")),
            "matchday_number": match.get("matchday_number"),
            "matchday_name": match.get("matchday_name"),
            "matchday_name_en": match.get("matchday_name_en"),
            "status": match.get("status"),
        }
        payload = {k: v for k, v in payload.items() if k in columns}
        if any(payload.get(k) is None for k in REQUIRED_COLUMNS):
            raise RuntimeError("Missing required fields for SportMonks match upsert")

        conn.execute(sql, payload)
        row = conn.execute(
            text("""
                select match_id, external_match_id, last_event_id
                from referee_ratings.matches
                where external_provider = :provider
                  and external_match_id = :fixture_id
                limit 1
            """),
            {
                "provider": "sportmonks",
                "fixture_id": _coerce_str(match.get("external_match_id")),
            },
        ).mappings().first()
        return dict(row) if row else None


def insert_new_events(
    provider: str,
    fixture_id: str,
    events: Iterable[Dict[str, Any]],
    last_event_id: Optional[int],
) -> Tuple[int, Optional[int]]:
    inserted = 0
    max_event_id = last_event_id
    sql = text("""
        insert into referee_ratings.match_events
          (provider, fixture_id, event_id, payload)
        values
          (:provider, :fixture_id, :event_id, :payload::jsonb)
        on conflict (provider, fixture_id, event_id)
        do nothing
    """)
    with engine.begin() as conn:
        for event in events:
            if not isinstance(event, dict):
                continue
            raw_id = event.get("id")
            if raw_id is None:
                continue
            try:
                event_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if last_event_id is not None and event_id <= last_event_id:
                continue
            result = conn.execute(sql, {
                "provider": provider,
                "fixture_id": str(fixture_id),
                "event_id": event_id,
                "payload": event,
            })
            if result.rowcount:
                inserted += 1
            if max_event_id is None or event_id > max_event_id:
                max_event_id = event_id
    return inserted, max_event_id


def update_poll_state(
    match_id: Optional[str],
    fixture_id: Optional[str],
    last_event_id: Optional[int],
    polled_at: Optional[datetime] = None,
) -> None:
    if not match_id and not fixture_id:
        return
    polled_at = polled_at or datetime.now(timezone.utc)
    if match_id:
        sql = text("""
            update referee_ratings.matches
            set last_polled_at = :polled_at,
                last_event_id = :last_event_id
            where match_id = cast(:match_id as uuid)
        """)
        params = {
            "polled_at": polled_at,
            "last_event_id": last_event_id,
            "match_id": str(match_id),
        }
    else:
        sql = text("""
            update referee_ratings.matches
            set last_polled_at = :polled_at,
                last_event_id = :last_event_id
            where external_provider = 'sportmonks'
              and external_match_id = :fixture_id
        """)
        params = {
            "polled_at": polled_at,
            "last_event_id": last_event_id,
            "fixture_id": str(fixture_id),
        }
    with engine.begin() as conn:
        conn.execute(sql, params)
