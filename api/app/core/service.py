from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from app.core import settings
from app.core.sportmonks.client import SportMonksClient
from app.core.sportmonks.mapper import map_fixture_to_match
from app.core.sportmonks.repository import (
    insert_new_events,
    update_poll_state,
    upsert_match_from_sportmonks_fixture,
    upsert_matches,
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

def _extract_events(fixture: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    events = fixture.get("events")
    if isinstance(events, dict):
        data = events.get("data")
        if isinstance(data, list):
            return data
    if isinstance(events, list):
        return events
    return []


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


def poll_inplay_and_persist() -> Dict[str, int]:
    if not settings.SPORTMONKS_ENABLED:
        raise RuntimeError("SPORTMONKS_ENABLED is false")

    include = "participants;scores;periods;events;league.country;round"
    client = SportMonksClient(get_sportmonks_api_token())
    fixtures_processed = 0
    events_inserted = 0
    try:
        payload = client.get_livescores_inplay(include=include)
        fixtures = _extract_fixtures(payload)
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            upserted = upsert_match_from_sportmonks_fixture(fixture)
            if not upserted:
                continue
            fixtures_processed += 1
            fixture_id = str(fixture.get("id"))
            last_event_id = upserted.get("last_event_id")
            inserted, max_event_id = insert_new_events(
                "sportmonks",
                fixture_id,
                _extract_events(fixture),
                last_event_id,
            )
            events_inserted += inserted
            update_poll_state(
                upserted.get("match_id"),
                fixture_id,
                max_event_id if max_event_id is not None else last_event_id,
            )
    finally:
        client.close()

    return {
        "fixtures_processed": fixtures_processed,
        "events_inserted": events_inserted,
    }
