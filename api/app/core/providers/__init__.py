from __future__ import annotations

import logging
from typing import Protocol

from app.core import settings
from app.core.providers.sportmonks import SportMonksProvider


logger = logging.getLogger("uvicorn.error")


class MatchesProvider(Protocol):
    """Marker protocol for match providers."""
    pass


class OpenLigaDBProvider:
    """Default provider stub."""
    pass


def get_match_provider() -> MatchesProvider:
    if settings.get_active_match_provider() == "sportmonks":
        logger.info("provider=sportmonks selected")
        return SportMonksProvider()
    return OpenLigaDBProvider()
