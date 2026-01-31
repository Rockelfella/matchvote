from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID, uuid5, NAMESPACE_URL

from app.core.sportmonks.league_mapping import get_league_mapping_by_provider_ids


_FIXTURE_NAMESPACE = uuid5(NAMESPACE_URL, "matchvote:sportmonks:fixture")


def _fixture_uuid(fixture_id: int) -> UUID:
    return uuid5(_FIXTURE_NAMESPACE, str(fixture_id))


def _coerce_team(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def map_schedule_row_to_match(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fixture_id = row.get("fixture_id")
    if fixture_id is None:
        return None
    mapping = get_league_mapping_by_provider_ids(
        row.get("league_id"),
        row.get("season_id"),
    )
    if not mapping:
        return None
    team_home = _coerce_team(row.get("home_id"))
    team_away = _coerce_team(row.get("away_id"))
    if not team_home or not team_away:
        return None
    match_date = row.get("starts_at")
    if match_date is None:
        return None
    return {
        "match_id": _fixture_uuid(int(fixture_id)),
        "league": mapping.internal_league_code,
        "season": mapping.season_key,
        "match_date": match_date,
        "team_home": team_home,
        "team_away": team_away,
        "matchday_number": None,
        "matchday_name": None,
        "matchday_name_en": None,
    }


def map_schedule_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for row in rows:
        item = map_schedule_row_to_match(row)
        if item is not None:
            mapped.append(item)
    return mapped
