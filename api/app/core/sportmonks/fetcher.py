from __future__ import annotations

from typing import Any, Dict

from app.core.sportmonks import get_sportmonks_api_token
from app.core.sportmonks.client import SportMonksClient


def fetch_inplay_readonly(include: str) -> Dict[str, Any]:
    client = SportMonksClient(get_sportmonks_api_token())
    try:
        return client.get_livescores_inplay(include=include)
    finally:
        client.close()
