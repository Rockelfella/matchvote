from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


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


def _extract_participants(fixture: Dict[str, Any]) -> list[Dict[str, Any]]:
    participants = fixture.get("participants")
    if isinstance(participants, dict):
        data = participants.get("data")
        if isinstance(data, list):
            return data
    if isinstance(participants, list):
        return participants
    return []


def _normalize_status(raw_status: Any) -> str:
    if isinstance(raw_status, dict):
        raw_status = raw_status.get("name") or raw_status.get("short_name")
    if raw_status is None:
        return "scheduled"
    value = str(raw_status).strip().lower()
    if not value:
        return "scheduled"
    if value in {"scheduled", "not_started", "ns", "upcoming", "tbd"}:
        return "scheduled"
    if value in {"live", "inplay", "in_play", "1h", "2h", "ht", "et"}:
        return "live"
    if value in {"finished", "ft", "full_time", "ended"}:
        return "finished"
    if any(token in value for token in ("postponed", "canceled", "cancelled", "suspended")):
        return "postponed"
    return "scheduled"


def map_fixture_to_match(fixture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    external_match_id = fixture.get("id")
    if external_match_id is None:
        return None
    kickoff = (
        _parse_datetime(fixture.get("starting_at"))
        or _parse_datetime(fixture.get("kickoff"))
        or _parse_datetime(fixture.get("starting_at_timestamp"))
    )

    home_team_id = None
    away_team_id = None
    home_team_name = None
    away_team_name = None

    for participant in _extract_participants(fixture):
        meta = participant.get("meta") if isinstance(participant, dict) else None
        location = None
        if isinstance(meta, dict):
            location = meta.get("location") or meta.get("side")
        participant_id = participant.get("id") if isinstance(participant, dict) else None
        participant_name = participant.get("name") if isinstance(participant, dict) else None

        if location == "home":
            home_team_id = participant_id
            home_team_name = participant_name
        elif location == "away":
            away_team_id = participant_id
            away_team_name = participant_name

    league_id = fixture.get("league_id")
    if league_id is None and isinstance(fixture.get("league"), dict):
        league_id = fixture["league"].get("id")

    status = _normalize_status(fixture.get("state") or fixture.get("status"))

    season_id = fixture.get("season_id")
    if season_id is None and isinstance(fixture.get("season"), dict):
        season_id = fixture["season"].get("id")

    return {
        "external_provider": "sportmonks",
        "external_match_id": external_match_id,
        "kickoff": kickoff,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "league_id": league_id,
        "status": status,
        "season_id": season_id,
        "home_team_name": home_team_name,
        "away_team_name": away_team_name,
    }
