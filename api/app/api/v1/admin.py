from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import text
from uuid import UUID
from app.core.admin_auth import require_admin_basic
from app.db import engine
from app.core.admin_auth import require_admin_basic

router = APIRouter(
    prefix="/v1/scenes",
    tags=["admin"],
    dependencies=[Depends(require_admin_basic)]
)


@router.patch("/{scene_id}/release", status_code=status.HTTP_200_OK)
def release_scene(scene_id: UUID):
    # Nur freigeben, wenn existiert und nicht gelockt
    sql = text("""
        update referee_ratings.scenes
           set is_released = true,
               release_time = now()
         where scene_id = cast(:scene_id as uuid)
           and is_locked = false
        returning scene_id, is_released, release_time
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()

        if row:
            return dict(row)

        # Differenzieren: nicht gefunden vs gelockt
        check = conn.execute(
            text("select is_locked from referee_ratings.scenes where scene_id = cast(:scene_id as uuid)"),
            {"scene_id": str(scene_id)}
        ).mappings().first()

        if not check:
            raise HTTPException(status_code=404, detail="Scene not found")

        raise HTTPException(status_code=409, detail="Scene is locked")


@router.patch("/{scene_id}/unrelease", status_code=status.HTTP_200_OK)
def unrelease_scene(scene_id: UUID):
    sql = text("""
        update referee_ratings.scenes
           set is_released = false,
               release_time = null
         where scene_id = cast(:scene_id as uuid)
           and is_locked = false
        returning scene_id, is_released
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()

        if row:
            return dict(row)

        check = conn.execute(
            text("select is_locked from referee_ratings.scenes where scene_id = cast(:scene_id as uuid)"),
            {"scene_id": str(scene_id)}
        ).mappings().first()

        if not check:
            raise HTTPException(status_code=404, detail="Scene not found")

        raise HTTPException(status_code=409, detail="Scene is locked")


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(scene_id: UUID):
    sql = text("""
        delete from referee_ratings.scenes
         where scene_id = cast(:scene_id as uuid)
           and is_locked = false
        returning scene_id
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).first()

        if row:
            return

        check = conn.execute(
            text("select is_locked from referee_ratings.scenes where scene_id = cast(:scene_id as uuid)"),
            {"scene_id": str(scene_id)}
        ).mappings().first()

        if not check:
            raise HTTPException(status_code=404, detail="Scene not found")

        raise HTTPException(status_code=409, detail="Scene is locked")
