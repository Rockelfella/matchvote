from __future__ import annotations

import argparse
import sys
import traceback

from app.core import settings
from app.core.sportmonks import get_sportmonks_api_token
from app.core.sportmonks.client import SportMonksClient
from app.core.sportmonks.normalizer import normalize_fixture
from app.core.sportmonks.service import poll_inplay_and_persist, sync_league_schedule


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

    return parser


def _run_sync_schedules(args: argparse.Namespace) -> int:
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
            f"updated={result['updated']} skipped={result['skipped']}"
        )
        for key in total:
            total[key] += result.get(key, 0)
    print(
        f"[sync-schedules] done processed={total['processed']} "
        f"inserted={total['inserted']} updated={total['updated']} skipped={total['skipped']}"
    )
    return 0


def _run_poll_inplay(_args: argparse.Namespace) -> int:
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
    if settings.get_active_match_provider() != "sportmonks":
        print("[shadow] provider != sportmonks -> exit 0")
        return 0

    settings.validate_settings()

    client = SportMonksClient(get_sportmonks_api_token())
    try:
        payload = client.get_livescores_inplay(
            include="participants;events;league;season",
        )
    finally:
        client.close()

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
        "[shadow] matches={matches} events={events} match_ids={match_ids} event_ids={event_ids}".format(
            matches=len(match_ids),
            events=len(event_ids),
            match_ids=",".join(match_ids[:limit]),
            event_ids=",".join(event_ids[:limit]),
        )
    )
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
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
