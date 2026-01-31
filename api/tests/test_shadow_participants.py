from __future__ import annotations

import json
from pathlib import Path

from app.core.providers.sportmonks.participants import parse_participants_from_schedules


def test_parse_participants_from_fixture():
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "sportmonks"
        / "schedules_example.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    rows = parse_participants_from_schedules(payload)

    assert len(rows) == 6
    participant_ids = {row["participant_id"] for row in rows}
    assert participant_ids == {2708, 683, 3543, 794, 3319, 2831}
    locations = {row["location"] for row in rows}
    assert locations == {"home", "away"}
