from __future__ import annotations

import argparse
import sys
import traceback

from app.core import settings
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


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.command == "sync-schedules":
            return _run_sync_schedules(args)
        if args.command == "poll-inplay":
            return _run_poll_inplay(args)
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
