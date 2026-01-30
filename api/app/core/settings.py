import os


_TRUTHY = {"1", "true", "yes", "on"}
_VALID_MATCH_PROVIDERS = {"openligadb", "sportmonks"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY


def _resolve_active_match_provider() -> str:
    value = os.environ.get("ACTIVE_MATCH_PROVIDER")
    if value and value.strip():
        candidate = value.strip().lower()
        if candidate in _VALID_MATCH_PROVIDERS:
            return candidate
        return "openligadb"
    if _env_flag("SPORTMONKS_ENABLED", default=False):
        return "sportmonks"
    return "openligadb"


ACTIVE_MATCH_PROVIDER = _resolve_active_match_provider()


def get_active_match_provider() -> str:
    return ACTIVE_MATCH_PROVIDER


def is_sportmonks_active() -> bool:
    return ACTIVE_MATCH_PROVIDER == "sportmonks"


SPORTMONKS_ENABLED = is_sportmonks_active()


def validate_settings() -> None:
    if not is_sportmonks_active():
        return
    token = os.environ.get("SPORTMONKS_API_TOKEN")
    if token is None or not token.strip():
        raise RuntimeError(
            "SPORTMONKS_API_TOKEN is required when ACTIVE_MATCH_PROVIDER=sportmonks"
        )
