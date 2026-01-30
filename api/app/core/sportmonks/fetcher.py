from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Tuple

import httpx

from app.core.sportmonks import get_sportmonks_api_token
from app.core.sportmonks.client import SPORTMONKS_BASE_URL


def fetch_inplay_readonly(include: str) -> Tuple[Dict[str, Any], int, int]:
    api_token = get_sportmonks_api_token()
    with httpx.Client(base_url=SPORTMONKS_BASE_URL, timeout=20.0) as client:
        response = client.get(
            "/livescores/inplay",
            params={"api_token": api_token, "include": include},
        )
    payload_size = len(response.content or b"")
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return payload, response.status_code, payload_size


def fetch_schedule_readonly(days: int) -> Tuple[Dict[str, Any], int, int]:
    api_token = get_sportmonks_api_token()
    start = date.today()
    end = start + timedelta(days=max(0, int(days)))
    client = SportMonksClient(api_token)
    try:
        response = client._client.get(
            f"/fixtures/between/{start.isoformat()}/{end.isoformat()}",
            params={"api_token": api_token, "include": "participants"},
        )
        payload_size = len(response.content or b"")
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return payload, response.status_code, payload_size
    finally:
        client.close()
