import os


_TRUTHY = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY


SPORTMONKS_ENABLED = _env_flag("SPORTMONKS_ENABLED", default=False)


def validate_settings() -> None:
    if not SPORTMONKS_ENABLED:
        return
    token = os.environ.get("SPORTMONKS_API_TOKEN")
    if token is None or not token.strip():
        raise RuntimeError(
            "SPORTMONKS_API_TOKEN is required when SPORTMONKS_ENABLED=true"
        )
