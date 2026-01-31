from fastapi import APIRouter, Depends, status

from app.core.admin_auth import require_admin_basic
from app.core.sportmonks.service import sync_team_schedule
from app.core.sportmonks.inplay_repository import get_inplay_snapshot

router = APIRouter(
    prefix="/admin/sportmonks",
    tags=["admin"],
    dependencies=[Depends(require_admin_basic)],
)


@router.post("/sync/team/{team_id}", status_code=status.HTTP_200_OK)
def sync_team(team_id: int):
    inserted = sync_team_schedule(team_id)
    return {"team_id": team_id, "matches_synced": inserted}


@router.post("/poll/inplay", status_code=status.HTTP_200_OK)
def poll_inplay():
    snapshot = get_inplay_snapshot()
    return {
        "matches_upserted": 0,
        "last_fetched_at": snapshot.get("last_fetched_at"),
        "fixtures": snapshot.get("fixtures"),
    }
