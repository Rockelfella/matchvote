from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

import app.main as main
from app.core.user_auth import require_user


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return 1


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        return _FakeResult(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return _FakeConnection(self._rows)

    def begin(self):
        return _FakeConnection(self._rows)


def _build_client(monkeypatch):
    monkeypatch.setattr(main, "init_db", None)
    main.app.dependency_overrides[require_user] = (
        lambda: "00000000-0000-0000-0000-000000000000"
    )
    return TestClient(main.app)


def test_matches_response_shape_unchanged(monkeypatch):
    from app.api.v1 import matches as matches_api

    match_row = {
        "match_id": UUID("00000000-0000-0000-0000-000000000000"),
        "league": "BL1",
        "season": "2024/25",
        "match_date": datetime(2024, 10, 1, 18, 0, tzinfo=timezone.utc),
        "team_home": "Home FC",
        "team_away": "Away FC",
        "matchday_number": 1,
        "matchday_name": "Matchday 1",
        "matchday_name_en": "Matchday 1",
    }
    monkeypatch.setattr(matches_api, "engine", _FakeEngine([match_row]))

    client = _build_client(monkeypatch)
    response = client.get("/matches")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert data
    assert set(data[0].keys()) == {
        "match_id",
        "league",
        "season",
        "match_date",
        "team_home",
        "team_away",
        "matchday_number",
        "matchday_name",
        "matchday_name_en",
    }


def test_accept_language_no_4xx(monkeypatch):
    from app.api.v1 import scenes as scenes_api

    monkeypatch.setattr(scenes_api, "engine", _FakeEngine([]))

    client = _build_client(monkeypatch)
    response = client.get("/scenes", headers={"Accept-Language": "de,zz;q=0.1"})
    assert response.status_code < 400
