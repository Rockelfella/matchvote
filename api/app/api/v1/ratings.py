from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.schemas.ratings import RatingCreate, RatingOut

from fastapi import Depends
from app.core.user_auth import require_user

router = APIRouter(prefix="/ratings", tags=["ratings"], dependencies=[Depends(require_user)])

@router.get("/me/{scene_id}", response_model=RatingOut)
def get_my_rating(scene_id: UUID, user_id: str = Depends(require_user)):
    sql = text("""
        select rating_id, scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, fav_team, created_at
        from referee_ratings.ratings
        where scene_id = :scene_id and user_id = :user_id
        limit 1
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id), "user_id": user_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Rating not found")
    return dict(row)

@router.post("", response_model=RatingOut, status_code=201)
def create_rating(payload: RatingCreate, user_id: str = Depends(require_user)):
    # 1) Szene muss existieren + released + nicht locked
    check_scene = text("""
        select
          s.scene_id,
          s.is_released,
          s.is_locked,
          m.team_home,
          m.team_away
        from referee_ratings.scenes s
        join referee_ratings.matches m on m.match_id = s.match_id
        where s.scene_id = :scene_id
    """)

    insert_sql = text("""
        insert into referee_ratings.ratings
          (scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, fav_team)
        values
          (:scene_id, :user_id, :decision_score, :confidence_score, :perception_channel, :rule_knowledge, :rating_time_type, :fav_team)
        returning
          rating_id, scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, fav_team, created_at
    """)
    ensure_user_sql = text("""
        insert into referee_ratings.users (user_id, email_hash, password_hash)
        select
          m.user_id,
          encode(digest(lower(trim(m.email)), 'sha256'), 'hex'),
          m.password_hash
        from mv_users m
        where m.user_id = cast(:user_id as uuid)
        on conflict do nothing
    """)
    existing_sql = text("""
        select rating_id
        from referee_ratings.ratings
        where scene_id = :scene_id and user_id = :user_id
        limit 1
    """)

    with engine.begin() as conn:
        s = conn.execute(check_scene, {"scene_id": str(payload.scene_id)}).mappings().first()
        if not s:
            raise HTTPException(status_code=404, detail="Scene not found")
        if not s["is_released"]:
            raise HTTPException(status_code=409, detail="Scene not released yet")
        if s["is_locked"]:
            raise HTTPException(status_code=409, detail="Scene is locked")
        if payload.fav_team is not None:
            if payload.fav_team not in (s["team_home"], s["team_away"]):
                raise HTTPException(status_code=400, detail="fav_team must match the match teams")

        conn.execute(ensure_user_sql, {"user_id": user_id})

        existing = conn.execute(existing_sql, {
            "scene_id": str(payload.scene_id),
            "user_id": user_id,
        }).mappings().first()
        if existing:
            raise HTTPException(status_code=409, detail="User already rated this scene")

        try:
            row = conn.execute(insert_sql, {
                "scene_id": str(payload.scene_id),
                "user_id": user_id,
                "decision_score": payload.decision_score,
                "confidence_score": payload.confidence_score,
                "perception_channel": payload.perception_channel,
                "rule_knowledge": payload.rule_knowledge,
                "rating_time_type": payload.rating_time_type,
                "fav_team": payload.fav_team,
            }).mappings().first()
        except IntegrityError:
            recheck = conn.execute(existing_sql, {
                "scene_id": str(payload.scene_id),
                "user_id": user_id,
            }).mappings().first()
            if recheck:
                raise HTTPException(status_code=409, detail="User already rated this scene")
            raise HTTPException(status_code=500, detail="Rating insert failed")

    return dict(row)


@router.get("", response_model=list[RatingOut])
def list_ratings(scene_id: UUID | None = Query(default=None)):
    sql = text("""
        select rating_id, scene_id, user_id, decision_score, confidence_score, perception_channel, rule_knowledge, rating_time_type, fav_team, created_at
        from referee_ratings.ratings
        where (:scene_id is null or scene_id = :scene_id)
        order by created_at desc
        limit 200
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"scene_id": str(scene_id) if scene_id else None}).mappings().all()
    return [dict(r) for r in rows]
