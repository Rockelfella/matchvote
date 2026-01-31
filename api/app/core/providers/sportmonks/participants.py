from __future__ import annotations

from typing import Any


def _get_int(value: Any) -> int | None:
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


def _get_fixtures(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "fixtures", "schedule"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return candidate
    return []


def parse_participants_from_schedules(payload: dict | list) -> list[dict]:
    rows: list[dict] = []
    fixtures = _get_fixtures(payload)
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        fixture_id = _get_int(fixture.get("id"))
        participants = fixture.get("participants")
        if isinstance(participants, dict):
            participants = participants.get("data")
        if not isinstance(participants, list):
            continue
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            participant_id = _get_int(participant.get("id"))
            meta = participant.get("meta") if isinstance(participant.get("meta"), dict) else {}
            location = meta.get("location")
            if location not in ("home", "away"):
                location = None
            rows.append(
                {
                    "fixture_id": fixture_id,
                    "participant_id": participant_id,
                    "location": location,
                }
            )
    return rows
