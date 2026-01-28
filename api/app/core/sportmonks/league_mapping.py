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
