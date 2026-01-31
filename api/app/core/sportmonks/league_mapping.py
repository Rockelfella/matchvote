from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class LeagueSeasonMapping:
    internal_league_code: str
    season_key: str
    provider_league_id: int
    provider_season_id: int
    provider_stage_id: Optional[int] = None


_MAPPINGS: Dict[str, Dict[str, LeagueSeasonMapping]] = {
    "BL1": {
        "2025_26": LeagueSeasonMapping(
            internal_league_code="BL1",
            season_key="2025_26",
            provider_league_id=82,
            provider_season_id=25646,
            provider_stage_id=77476914,
        ),
    },
    "BL2": {
        # TODO: fill in the correct SportMonks IDs for BL2.
        "2025_26": LeagueSeasonMapping(
            internal_league_code="BL2",
            season_key="2025_26",
            provider_league_id=0,
            provider_season_id=0,
            provider_stage_id=None,
        ),
    },
}


def get_league_mapping(league_code: str, season_key: str) -> LeagueSeasonMapping:
    league_code = (league_code or "").strip().upper()
    season_key = (season_key or "").strip()
    mapping = _MAPPINGS.get(league_code, {}).get(season_key)
    if not mapping:
        raise RuntimeError(
            f"No SportMonks mapping found for league={league_code} season={season_key}"
        )
    if mapping.provider_league_id <= 0 or mapping.provider_season_id <= 0:
        raise RuntimeError(
            f"Invalid SportMonks mapping for league={league_code} season={season_key}"
        )
    return mapping


def get_league_mapping_by_provider_ids(
    provider_league_id: int | None,
    provider_season_id: int | None,
) -> Optional[LeagueSeasonMapping]:
    if not provider_league_id or not provider_season_id:
        return None
    for seasons in _MAPPINGS.values():
        for mapping in seasons.values():
            if (
                mapping.provider_league_id == provider_league_id
                and mapping.provider_season_id == provider_season_id
            ):
                return mapping
    return None


def resolve_provider_filters(
    league_code: Optional[str],
    season_key: Optional[str],
) -> tuple[list[int] | None, list[int] | None]:
    league_code = (league_code or "").strip().upper()
    season_key = (season_key or "").strip()
    if league_code and season_key:
        mapping = get_league_mapping(league_code, season_key)
        return [mapping.provider_league_id], [mapping.provider_season_id]
    if league_code:
        seasons = _MAPPINGS.get(league_code, {})
        league_ids = []
        season_ids = []
        for mapping in seasons.values():
            if mapping.provider_league_id > 0 and mapping.provider_season_id > 0:
                league_ids.append(mapping.provider_league_id)
                season_ids.append(mapping.provider_season_id)
        return league_ids or None, season_ids or None
    if season_key:
        league_ids = []
        season_ids = []
        for seasons in _MAPPINGS.values():
            mapping = seasons.get(season_key)
            if mapping and mapping.provider_league_id > 0 and mapping.provider_season_id > 0:
                league_ids.append(mapping.provider_league_id)
                season_ids.append(mapping.provider_season_id)
        return league_ids or None, season_ids or None
    return None, None
