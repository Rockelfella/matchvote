from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_start_time(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _extract_team_name(participants: Any, location: str) -> Optional[str]:
    if not isinstance(participants, list):
        return None
    for participant in participants:
        if not isinstance(participant, dict):
            continue
        meta = participant.get("meta")
        if isinstance(meta, dict) and meta.get("location") == location:
            return _safe_str(participant.get("name"))
    return None


def normalize_fixture(fixture: Any) -> Optional[Dict[str, Optional[str]]]:
    if not isinstance(fixture, dict):
        return None

    participants = fixture.get("participants")
    if isinstance(participants, dict):
        participants = participants.get("data")

    normalized = {
        "external_match_id": _safe_str(fixture.get("id")),
        "league": _safe_str(fixture.get("league_id") or (fixture.get("league") or {}).get("id")),
        "season": _safe_str(fixture.get("season_id") or (fixture.get("season") or {}).get("id")),
        "start_time": _parse_start_time(
            fixture.get("starting_at")
            or fixture.get("starting_at_timestamp")
            or fixture.get("start_time")
        ),
        "home_team": _extract_team_name(participants, "home"),
        "away_team": _extract_team_name(participants, "away"),
        "status": _safe_str(fixture.get("state") or fixture.get("status")),
    }

    if not normalized["external_match_id"]:
        return None
    return normalized
