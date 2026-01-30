from __future__ import annotations

from typing import Any, Iterable, Optional

from app.core.providers import get_match_provider


def get_provider() -> Any:
    """Return the selected match provider instance."""
    return get_match_provider()


def list_matches(*args: Any, **kwargs: Any) -> Iterable[Any]:
    """List matches from the selected provider.

    Placeholder: not implemented yet.
    """
    raise NotImplementedError("list_matches is not implemented")


def sync_matches(*args: Any, **kwargs: Any) -> int:
    """Sync matches from the selected provider.

    Placeholder: not implemented yet.
    """
    raise NotImplementedError("sync_matches is not implemented")


def list_events(*args: Any, **kwargs: Any) -> Iterable[Any]:
    """List events from the selected provider.

    Placeholder: not implemented yet.
    """
    raise NotImplementedError("list_events is not implemented")


def sync_events(*args: Any, **kwargs: Any) -> int:
    """Sync events from the selected provider.

    Placeholder: not implemented yet.
    """
    raise NotImplementedError("sync_events is not implemented")


def get_match(*args: Any, **kwargs: Any) -> Optional[Any]:
    """Fetch a single match from the selected provider.

    Placeholder: not implemented yet.
    """
    raise NotImplementedError("get_match is not implemented")
