from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import httpx

from app.core import settings
from app.core.providers.sportmonks.participants import parse_participants_from_schedules
from app.core.providers.sportmonks.schedules import parse_schedules
from app.core.sportmonks.fetcher import fetch_inplay_readonly, fetch_schedule_readonly
from app.core.sportmonks.normalizer import normalize_fixture


def _default_shadow_schedule_path() -> str:
    return str(
        Path(__file__).resolve().parents[3]
        / "api/tests/fixtures/sportmonks/schedules_example.json"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="matchvote", description="MatchVote CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync-schedules", help="Sync schedules from SportMonks")
    sync.add_argument("--league", choices=["BL1", "BL2"], help="League code")
    sync.add_argument("--season", required=True, help="Season key, e.g. 2025_26")
    sync.add_argument("--all", action="store_true", help="Sync all leagues")

    poll = subparsers.add_parser("poll-inplay", help="Poll SportMonks inplay fixtures")
    poll.add_argument("--league", choices=["BL1", "BL2"], help="Optional (not used)")
    poll.add_argument("--window", help="Optional (not used)")

    shadow = subparsers.add_parser(
        "sportmonks-shadow-inplay",
        help="Shadow read-only SportMonks inplay fetch",
    )
    shadow.add_argument("--limit", type=int, default=10, help="Limit IDs logged")

    shadow_schedule = subparsers.add_parser(
        "sportmonks-shadow-schedule",
        help="Shadow read-only SportMonks schedule fetch",
    )
    shadow_schedule.add_argument("--days", type=int, default=7, help="Days window")

    shadow = subparsers.add_parser("shadow", help="Shadow SportMonks workflows")
    shadow_sub = shadow.add_subparsers(dest="shadow_command", required=True)

    shadow_schedules = shadow_sub.add_parser(
        "schedules",
        help="Shadow read-only SportMonks schedules (file-based)",
    )
    shadow_schedules.add_argument(
        "--from-file",
        default=_default_shadow_schedule_path(),
        help="Load schedules payload from JSON file",
    )
    shadow_schedules.add_argument(
        "--json",
        action="store_true",
        help="Print normalized fixtures as JSON",
    )

    shadow_participants = shadow_sub.add_parser(
        "participants",
        help="Shadow read-only SportMonks participants (file-based)",
    )
    shadow_participants.add_argument(
        "--from-file",
        default=_default_shadow_schedule_path(),
        help="Load schedules payload from JSON file",
    )
    shadow_participants.add_argument(
        "--json",
        action="store_true",
        help="Print normalized participants as JSON",
    )

    return parser


def _run_sync_schedules(args: argparse.Namespace) -> int:
    from app.core.sportmonks.service import sync_league_schedule

    if not settings.SPORTMONKS_ENABLED:
        print("[sportmonks] disabled")
        return 0
    leagues = ["BL1", "BL2"] if args.all else [args.league]
    if not leagues or leagues == [None]:
        raise RuntimeError("Provide --league or --all")

    total = {"processed": 0, "inserted": 0, "updated": 0, "skipped": 0}
    print(f"[sync-schedules] start season={args.season} leagues={','.join(leagues)}")
    for league in leagues:
        result = sync_league_schedule(league, args.season)
        print(
            f"[sync-schedules] league={league} "
            f"processed={result['processed']} inserted={result['inserted']} "
            f"updated={result['updated']} skipped={result.get('skipped', 0)}"
        )
        for key in total:
            total[key] += result.get(key, 0)
    print(
        f"[sync-schedules] done processed={total['processed']} "
        f"inserted={total['inserted']} updated={total['updated']} skipped={total['skipped']}"
    )
    return 0


def _run_poll_inplay(_args: argparse.Namespace) -> int:
    from app.core.sportmonks.service import poll_inplay_and_persist

    if not settings.SPORTMONKS_ENABLED:
        print("[sportmonks] disabled")
        return 0
    print("[poll-inplay] start")
    count = poll_inplay_and_persist()
    print(f"[poll-inplay] done matches_upserted={count}")
    return 0


def _extract_fixtures(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return data
    fixtures = payload.get("fixtures") if isinstance(payload, dict) else None
    if isinstance(fixtures, list):
        return fixtures
    return []


def _extract_events(fixture):
    events = fixture.get("events") if isinstance(fixture, dict) else None
    if isinstance(events, dict):
        data = events.get("data")
        if isinstance(data, list):
            return data
    if isinstance(events, list):
        return events
    return []


def _run_shadow_inplay(args: argparse.Namespace) -> int:
    if not settings.SPORTMONKS_ENABLED:
        print("[shadow] provider != sportmonks -> exit 0")
        return 0

    settings.validate_settings()

    try:
        payload, status_code, payload_size = fetch_inplay_readonly(
            include="participants;events;league;season"
        )
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        print(
            f"[shadow] sportmonks fetch failed: {exc.__class__.__name__} -> exit 0"
        )
        return 0

    fixtures = _extract_fixtures(payload)
    normalized = []
    event_ids = []
    for fixture in fixtures:
        normalized_item = normalize_fixture(fixture)
        if normalized_item:
            normalized.append(normalized_item)
        for event in _extract_events(fixture):
            if isinstance(event, dict):
                event_id = event.get("id")
                if event_id is not None:
                    event_ids.append(str(event_id))

    match_ids = [item["external_match_id"] for item in normalized if item.get("external_match_id")]
    limit = max(0, int(args.limit))
    print(
        "[shadow] inplay: status={status} payload_bytes={size} matches={matches} events={events}".format(
            status=status_code,
            size=payload_size,
            matches=len(match_ids),
            events=len(event_ids),
        )
    )
    if len(match_ids) == 0:
        reason = "http_error" if status_code != 200 else "no_live_matches"
        print(
            "[shadow] inplay: no live matches right now (matches=0, events=0, reason={reason})".format(
                reason=reason
            )
        )
    print(
        "[shadow] matches={matches} events={events} match_ids={match_ids} event_ids={event_ids}".format(
            matches=len(match_ids),
            events=len(event_ids),
            match_ids=",".join(match_ids[:limit]),
            event_ids=",".join(event_ids[:limit]),
        )
    )
    return 0


def _run_shadow_schedule(args: argparse.Namespace) -> int:
    if not settings.SPORTMONKS_ENABLED:
        print("[shadow] provider != sportmonks -> exit 0")
        return 0

    settings.validate_settings()

    try:
        payload, status_code, payload_size = fetch_schedule_readonly(days=args.days)
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        print(
            f"[shadow] sportmonks fetch failed: {exc.__class__.__name__} -> exit 0"
        )
        return 0

    fixtures = _extract_fixtures(payload)
    fixture_ids = []
    for fixture in fixtures:
        if isinstance(fixture, dict) and fixture.get("id") is not None:
            fixture_ids.append(str(fixture.get("id")))

    print(
        "[shadow] schedule: status={status} payload_bytes={size} fixtures={fixtures}".format(
            status=status_code,
            size=payload_size,
            fixtures=len(fixtures),
        )
    )
    if len(fixtures) == 0:
        print("[shadow] schedule: no fixtures in window (fixtures=0, reason=no_fixtures_in_window)")
    else:
        print(
            "[shadow] schedule: fixture_ids={ids}".format(
                ids=",".join(fixture_ids[:10])
            )
        )
    return 0


def _run_shadow_schedules(args: argparse.Namespace) -> int:
    if not settings.SPORTMONKS_ENABLED:
        print("[shadow] provider != sportmonks -> exit 0")
        return 0

    settings.validate_settings()

    payload_path = Path(args.from_file)
    with payload_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    normalized = parse_schedules(payload)
    fixture_ids = [
        str(item["fixture_id"])
        for item in normalized
        if item.get("fixture_id") is not None
    ]
    print(
        "[shadow] schedule: fixtures={count} fixture_ids={ids}".format(
            count=len(normalized),
            ids=",".join(fixture_ids),
        )
    )
    if args.json:
        print(json.dumps(normalized, indent=2))
    return 0


def _run_shadow_participants(args: argparse.Namespace) -> int:
    if not settings.SPORTMONKS_ENABLED:
        print("[shadow] provider != sportmonks -> exit 0")
        return 0

    settings.validate_settings()

    payload_path = Path(args.from_file)
    with payload_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    rows = parse_participants_from_schedules(payload)
    unique_participants = {row["participant_id"] for row in rows if row.get("participant_id") is not None}
    home_count = sum(1 for row in rows if row.get("location") == "home")
    away_count = sum(1 for row in rows if row.get("location") == "away")
    print(
        "[shadow] participants: rows={rows} unique_participants={unique} "
        "by_location=home:{home},away:{away}".format(
            rows=len(rows),
            unique=len(unique_participants),
            home=home_count,
            away=away_count,
        )
    )
    if args.json:
        print(json.dumps(rows, indent=2))
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.command == "sync-schedules":
            return _run_sync_schedules(args)
        if args.command == "poll-inplay":
            return _run_poll_inplay(args)
        if args.command == "sportmonks-shadow-inplay":
            return _run_shadow_inplay(args)
        if args.command == "sportmonks-shadow-schedule":
            return _run_shadow_schedule(args)
        if args.command == "shadow":
            if args.shadow_command == "schedules":
                return _run_shadow_schedules(args)
            if args.shadow_command == "participants":
                return _run_shadow_participants(args)
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
