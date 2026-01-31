from __future__ import annotations

from typing import Any, Dict

import httpx

SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"


class SportMonksClient:
    def __init__(self, api_token: str, base_url: str = SPORTMONKS_BASE_URL) -> None:
        self._api_token = api_token
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=20.0)

    def get_team_schedule(self, team_id: int) -> Dict[str, Any]:
        response = self._client.get(
            f"/schedules/teams/{team_id}",
            params={"api_token": self._api_token},
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"SportMonks request failed with status {response.status_code}"
            )
        return response.json()

    def get_league_schedule(self, league_id: int, season_id: int, include: str) -> Dict[str, Any]:
        path = "/fixtures"
        params = {
            "api_token": self._api_token,
            "season_id": season_id,
            "include": include,
            "league_id": league_id,
        }
        response = self._client.get(
            path,
            params=params,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"SportMonks request failed with status {response.status_code}"
            )
        return response.json()

    def get_livescores_inplay(self, include: str) -> Dict[str, Any]:
        response = self._client.get(
            "/livescores/inplay",
            params={
                "api_token": self._api_token,
                "include": include,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"SportMonks request failed with status {response.status_code}"
            )
        return response.json()

    def close(self) -> None:
        self._client.close()
