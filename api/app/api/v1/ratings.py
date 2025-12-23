from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.schemas.ratings import RatingCreate, RatingOut

router = APIRouter(prefix="/v1/ratings", tags=["Ratings"])


@router.post("", response_model=RatingOut, status_code=201)
def create_rating(payload: RatingCreate):
    # 1) Szene muss existieren + released + nicht locked
    check_scene = text("""
        select scene_id, is_released, is_locked
        from referee_ratings.scenes
        where scene_id = :scene_id
    """)

    insert_sql = text("""
        insert into referee_ratings.ratings
          (scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type)
        values
          (:scene_id, :user_id, :decision_score, :confidence_score, :perception_channel, :rule_knowledge, :rating_time_type)
        returning
          rating_id, scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, created_at
    """)

    with engine.begin() as conn:
        s = conn.execute(check_scene, {"scene_id": str(payload.scene_id)}).mappings().first()
        if not s:
            raise HTTPException(status_code=404, detail="Scene not found")
        if not s["is_released"]:
            raise HTTPException(status_code=409, detail="Scene not released yet")
        if s["is_locked"]:
            raise HTTPException(status_code=409, detail="Scene is locked")

        try:
            row = conn.execute(insert_sql, {
                "scene_id": str(payload.scene_id),
                "user_id": str(payload.user_id),
                "decision_score": payload.decision_score,
                "confidence_score": payload.confidence_score,
                "perception_channel": payload.perception_channel,
                "rule_knowledge": payload.rule_knowledge,
                "rating_time_type": payload.rating_time_type,
            }).mappings().first()
        except IntegrityError:
            # UNIQUE(scene_id, user_id) -> schon bewertet
            raise HTTPException(status_code=409, detail="User already rated this scene")

    return dict(row)


@router.get("", response_model=list[RatingOut])
def list_ratings(scene_id: UUID | None = Query(default=None)):
    sql = text("""
        select rating_id, scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, created_at
        from referee_ratings.ratings
        where (:scene_id is null or scene_id = :scene_id)
        order by created_at desc
        limit 200
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"scene_id": str(scene_id) if scene_id else None}).mappings().all()
    return [dict(r) for r in rows]
