from __future__ import annotations

import os
from typing import Optional

from app.core import settings
from app.core.sportmonks.client import SportMonksClient

_sportmonks_client: Optional[SportMonksClient] = None


def get_sportmonks_api_token() -> str:
    token = os.environ.get("SPORTMONKS_API_TOKEN")
    if token is None or not token.strip():
        raise RuntimeError("SPORTMONKS_API_TOKEN is not set")
    return token


def init_sportmonks_client() -> Optional[SportMonksClient]:
    global _sportmonks_client
    if not settings.is_sportmonks_active():
        _sportmonks_client = None
        return None
    _sportmonks_client = SportMonksClient(get_sportmonks_api_token())
    return _sportmonks_client


def get_sportmonks_client() -> SportMonksClient:
    if _sportmonks_client is None:
        client = init_sportmonks_client()
        if client is None:
            raise RuntimeError("SportMonks client is not initialized")
        return client
    return _sportmonks_client
