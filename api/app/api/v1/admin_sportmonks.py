from fastapi import APIRouter, Depends, status

from app.core.admin_auth import require_admin_basic
from app.core.sportmonks.service import poll_inplay_and_persist, sync_team_schedule

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
    result = poll_inplay_and_persist()
    return {"matches_upserted": result}
