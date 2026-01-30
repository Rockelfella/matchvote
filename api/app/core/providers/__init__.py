from app.core import settings
from app.core.providers.sportmonks import SportMonksProvider


class OpenLigaDBProvider:
    pass


def get_match_provider():
    if settings.SPORTMONKS_ENABLED:
        return SportMonksProvider()
    return OpenLigaDBProvider()
