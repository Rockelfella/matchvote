from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core import settings
from app.core.sportmonks.client import SportMonksClient
from app.core.sportmonks.mapper import map_fixture_to_match
from app.core.sportmonks.league_mapping import get_league_mapping
from app.core.sportmonks.repository import upsert_matches, upsert_schedule_matches
from app.core.sportmonks.schedule_repository import (
    insert_schedule_raw,
    upsert_schedule_fixtures,
)
from app.core.sportmonks.inplay_repository import (
    insert_inplay_raw,
    upsert_inplay_state,
)
from app.core.sportmonks import get_sportmonks_api_token

logger = logging.getLogger("uvicorn.error")


def _extract_fixtures(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return data
    fixtures = payload.get("fixtures")
    if isinstance(fixtures, list):
        return fixtures
    return []


def _extract_schedule_stages(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def _iter_schedule_fixtures(
    stages: List[Dict[str, Any]]
) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]]:
    for stage in stages:
        rounds = stage.get("rounds")
        if isinstance(rounds, list) and rounds:
            for round_item in rounds:
                fixtures = round_item.get("fixtures")
                if isinstance(fixtures, list):
                    for fixture in fixtures:
                        if isinstance(fixture, dict):
                            yield fixture, stage, round_item
            continue
        fixtures = stage.get("fixtures")
        if isinstance(fixtures, list):
            for fixture in fixtures:
                if isinstance(fixture, dict):
                    yield fixture, stage, None


def _parse_matchday(
    round_item: Optional[Dict[str, Any]]
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    if not round_item:
        return None, None, None
    name = round_item.get("name")
    if name is None:
        return None, None, None
    name_str = str(name).strip()
    if not name_str:
        return None, None, None
    number = None
    try:
        number = int(name_str)
    except ValueError:
        number = None
    name_en = f"Matchday {number}" if number is not None else None
    return number, name_str, name_en


def _map_schedule_fixture(
    fixture: Dict[str, Any],
    stage: Dict[str, Any],
    round_item: Optional[Dict[str, Any]],
    league_code: str,
    season_key: str,
) -> Optional[Dict[str, Any]]:
    base = map_fixture_to_match(fixture)
    if base is None:
        return None
    matchday_number, matchday_name, matchday_name_en = _parse_matchday(round_item)
    return {
        "external_match_id": base.get("external_match_id"),
        "league": league_code,
        "season": season_key,
        "match_date": base.get("kickoff"),
        "team_home": base.get("home_team_name") or base.get("home_team_id"),
        "team_away": base.get("away_team_name") or base.get("away_team_id"),
        "status": base.get("status"),
        "matchday_number": matchday_number,
        "matchday_name": matchday_name,
        "matchday_name_en": matchday_name_en,
        "provider_league_id": fixture.get("league_id") or stage.get("league_id"),
        "provider_season_id": fixture.get("season_id") or stage.get("season_id"),
        "provider_stage_id": fixture.get("stage_id") or stage.get("id"),
        "provider_round_id": fixture.get("round_id") if isinstance(round_item, dict) else None,
    }


def sync_team_schedule(team_id: int) -> int:
    if not settings.SPORTMONKS_ENABLED:
        raise RuntimeError("SPORTMONKS_ENABLED is false")

    client = SportMonksClient(get_sportmonks_api_token())
    try:
        payload = client.get_team_schedule(team_id)
        fixtures = _extract_fixtures(payload)
        mapped = []
        for item in fixtures:
            match = map_fixture_to_match(item)
            if match is None:
                fixture_id = item.get("id") if isinstance(item, dict) else None
                logger.warning(
                    "Skipping SportMonks fixture without required fields (fixture_id=%s)",
                    fixture_id,
                )
                continue
            mapped.append(match)
        return upsert_matches(mapped)
    finally:
        client.close()


def sync_league_schedule(league_code: str, season_key: str) -> Dict[str, int]:
    if not settings.SPORTMONKS_ENABLED:
        raise RuntimeError("SPORTMONKS_ENABLED is false")

    mapping = get_league_mapping(league_code, season_key)
    client = SportMonksClient(get_sportmonks_api_token())
    try:
        fetched_at = datetime.now(timezone.utc)
        payload = client.get_league_schedule(
            mapping.provider_league_id,
            mapping.provider_season_id,
            include="participants",
        )
        request_params = {
            "league_id": mapping.provider_league_id,
            "season_id": mapping.provider_season_id,
            "include": "participants",
        }
        insert_schedule_raw(payload, request_params, fetched_at=fetched_at)
        result = upsert_schedule_fixtures(payload, fetched_at=fetched_at)
        logger.info(
            "sportmonks schedule fetched league=%s season=%s fixtures=%s fetched_at=%s",
            league_code,
            season_key,
            result.get("processed"),
            fetched_at.isoformat(),
        )
        return result
    finally:
        client.close()


def poll_inplay_and_persist() -> int:
    if not settings.SPORTMONKS_ENABLED:
        raise RuntimeError("SPORTMONKS_ENABLED is false")

    client = SportMonksClient(get_sportmonks_api_token())
    try:
        fetched_at = datetime.now(timezone.utc)
        include = "participants;scores;periods;events;league.country;round"
        payload = client.get_livescores_inplay(include=include)
        insert_inplay_raw(
            payload,
            {"include": include},
            fetched_at=fetched_at,
        )
        state_result = upsert_inplay_state(payload, fetched_at=fetched_at)
        fixtures = _extract_fixtures(payload)
        mapped = []
        for item in fixtures:
            match = map_fixture_to_match(item)
            if match is None:
                continue
            mapped.append(match)

        # vorerst nur Matches upserten (Events später)
        upsert_matches(mapped)
        logger.info(
            "sportmonks inplay fetched fixtures=%s stored=%s fetched_at=%s",
            len(mapped),
            state_result.get("processed"),
            fetched_at.isoformat(),
        )
        return len(mapped)
    finally:
        client.close()
