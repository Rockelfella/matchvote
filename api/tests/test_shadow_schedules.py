from __future__ import annotations

import json
from pathlib import Path

from app.core.providers.sportmonks.schedules import parse_schedules


def test_parse_schedules_from_fixture():
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "sportmonks"
        / "schedules_example.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    normalized = parse_schedules(payload)

    assert len(normalized) == 3
    fixture_ids = [item["fixture_id"] for item in normalized]
    assert fixture_ids == [19428180, 19428181, 19428182]
    for item in normalized:
        assert "fixture_id" in item
        assert "starts_at" in item
        assert "status" in item
