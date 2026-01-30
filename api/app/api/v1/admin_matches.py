from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.deps import require_admin
from app.core.matches.provider_service import get_provider as get_matches_provider
from app.db import engine

router = APIRouter(
    prefix="/admin/matches",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(get_matches_provider)],
)


@router.delete("/{match_id}", status_code=204)
def delete_match(match_id: UUID):
    with engine.begin() as conn:
        row = conn.execute(
            text("select match_id from referee_ratings.matches where match_id = :mid"),
            {"mid": str(match_id)},
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Match not found")

        scene_count = conn.execute(
            text("select count(*) from referee_ratings.scenes where match_id = :mid"),
            {"mid": str(match_id)},
        ).scalar()
        if scene_count and scene_count > 0:
            raise HTTPException(status_code=409, detail="Match has scenes")

        conn.execute(
            text("delete from referee_ratings.matches where match_id = :mid"),
            {"mid": str(match_id)},
        )
