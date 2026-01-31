import os


_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY


SPORTMONKS_ENABLED = _env_flag("SPORTMONKS_ENABLED", default=False)
_raw_sportmonks_token = os.environ.get("SPORTMONKS_API_TOKEN")
SPORTMONKS_API_TOKEN = (
    _raw_sportmonks_token.strip()
    if _raw_sportmonks_token and _raw_sportmonks_token.strip()
    else None
)

ACTIVE_MATCH_PROVIDER = "sportmonks" if SPORTMONKS_ENABLED else "openligadb"


def get_active_match_provider() -> str:
    return ACTIVE_MATCH_PROVIDER


def is_sportmonks_active() -> bool:
    return SPORTMONKS_ENABLED


def validate_settings() -> None:
    if not SPORTMONKS_ENABLED:
        return
    if not SPORTMONKS_API_TOKEN:
        raise ValueError(
            "SPORTMONKS_API_TOKEN is required when SPORTMONKS_ENABLED=true"
        )
