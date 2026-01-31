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


def _get_str(value: Any) -> str | None:
    if isinstance(value, str):
        raw = value.strip()
        return raw if raw else None
    return None


def _get_nested_int(payload: dict, *keys: str) -> int | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _get_int(current)


def _extract_status(fixture: dict) -> str | None:
    state_id = _get_int(fixture.get("state_id"))
    if state_id is not None:
        return str(state_id)
    status = fixture.get("status")
    if isinstance(status, dict):
        return _get_str(status.get("short")) or _get_str(status.get("name"))
    return _get_str(status) or _get_str(fixture.get("state"))


def _extract_starts_at(fixture: dict) -> str | None:
    value = _get_str(fixture.get("starting_at"))
    if value:
        return value
    return _get_str(fixture.get("starts_at"))


def _extract_team_ids(fixture: dict) -> tuple[int | None, int | None]:
    home_id = (
        _get_int(fixture.get("home_team_id"))
        or _get_int(fixture.get("home_id"))
        or _get_nested_int(fixture, "localteam", "id")
    )
    away_id = (
        _get_int(fixture.get("away_team_id"))
        or _get_int(fixture.get("away_id"))
        or _get_nested_int(fixture, "visitorteam", "id")
    )

    participants = fixture.get("participants")
    if isinstance(participants, dict):
        participants = participants.get("data")
    if isinstance(participants, list):
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            team_id = _get_int(participant.get("id"))
            meta = participant.get("meta") if isinstance(participant.get("meta"), dict) else {}
            location = _get_str(meta.get("location")) or _get_str(meta.get("type"))
            if location == "home" and home_id is None:
                home_id = team_id
            elif location == "away" and away_id is None:
                away_id = team_id

    return home_id, away_id


def parse_schedules(payload: Any) -> list[dict]:
    fixtures: list[Any] = []
    if isinstance(payload, list):
        fixtures = payload
    elif isinstance(payload, dict):
        for key in ("data", "fixtures", "schedule"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                fixtures = candidate
                break

    normalized: list[dict] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        home_team_id, away_team_id = _extract_team_ids(fixture)
        normalized.append(
            {
                "fixture_id": _get_int(fixture.get("id")),
                "league_id": _get_int(fixture.get("league_id"))
                or _get_nested_int(fixture, "league", "id"),
                "season_id": _get_int(fixture.get("season_id"))
                or _get_nested_int(fixture, "season", "id"),
                "round_id": _get_int(fixture.get("round_id"))
                or _get_nested_int(fixture, "round", "id"),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "starts_at": _extract_starts_at(fixture),
                "status": _extract_status(fixture),
            }
        )
    return normalized
