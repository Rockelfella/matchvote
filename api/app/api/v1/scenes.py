from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from uuid import UUID
from typing import List, Optional

from app.db import engine
from app.schemas.scenes import SceneCreate, SceneOut

from datetime import datetime, timezone
from sqlalchemy import text
from app.schemas.ratings import SceneAggregateOut
from uuid import UUID
from fastapi import HTTPException

router = APIRouter(prefix="/v1/scenes", tags=["scenes"])

@router.get("", response_model=List[SceneOut])
def list_scenes(match_id: Optional[UUID] = None, limit: int = 50, offset: int = 0):
    if match_id:
        sql = text("""
            select
              scene_id,
              match_id,
              minute,
              stoppage_time,
              scene_type,
              description,
              is_released,
              release_time,
              created_by,
              created_at
            from referee_ratings.scenes
            where match_id = :match_id
            order by created_at desc nulls last
            limit :limit offset :offset
        """)
        params = {"match_id": str(match_id), "limit": limit, "offset": offset}
    else:
        sql = text("""
            select
              scene_id,
              match_id,
              minute,
              stoppage_time,
              scene_type,
              description,
              is_released,
              release_time,
              created_by,
              created_at
            from referee_ratings.scenes
            order by created_at desc nulls last
            limit :limit offset :offset
        """)
        params = {"limit": limit, "offset": offset}

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return rows

@router.get("/{scene_id}", response_model=SceneOut)
def get_scene(scene_id: UUID):
    sql = text("""
        select
          scene_id,
          match_id,
          minute,
          stoppage_time,
          scene_type,
          description,
          is_released,
          release_time,
          created_by,
          created_at
        from referee_ratings.scenes
        where scene_id = :scene_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    return row

@router.post("", response_model=SceneOut, status_code=201)
def create_scene(payload: SceneCreate):
    # created_by ist optional (bis JWT kommt)
    sql = text("""
        insert into referee_ratings.scenes
          (match_id, minute, stoppage_time, scene_type, description, is_released, release_time, created_by)
        values
          (:match_id, :minute, :stoppage_time, :scene_type, :description, :is_released, :release_time, :created_by)
        returning
          scene_id,
          match_id,
          minute,
          stoppage_time,
          scene_type,
          description,
          is_released,
          release_time,
          created_by,
          created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {
            "match_id": str(payload.match_id),
            "minute": payload.minute,
            "stoppage_time": payload.stoppage_time,
            "scene_type": payload.scene_type,
            "description": payload.description,
            "is_released": payload.is_released,
            "release_time": payload.release_time,
            "created_by": str(payload.created_by) if payload.created_by else None,
        }).mappings().first()
    return row
@router.get("/{scene_id}/aggregate", response_model=SceneAggregateOut)
def scene_aggregate(scene_id: UUID):
    # scene exists?
    scene_sql = text("select scene_id from referee_ratings.scenes where scene_id = :scene_id")
    agg_sql = text("""
   with r as (
     select
      decision_score,
      confidence_score,
      perception_channel::text as perception_channel,
      rating_time_type::text as rating_time_type,
      rule_knowledge::text as rule_knowledge
      from referee_ratings.ratings
      where scene_id = cast(:scene_id as uuid)
    )
     select
      cast(:scene_id as uuid) as scene_id,
       (select count(*) from r) as rating_count,
       (select coalesce(avg(decision_score)::numeric, 0)::float from r) as avg_decision,
       (select coalesce(avg(confidence_score)::numeric, 0)::float from r) as avg_confidence,
       (select coalesce(jsonb_object_agg(decision_score::text, cnt), '{}'::jsonb)
         from (select decision_score, count(*) cnt from r group by decision_score order by decision_score) x) as decision_dist,
       (select coalesce(jsonb_object_agg(confidence_score::text, cnt), '{}'::jsonb)
         from (select confidence_score, count(*) cnt from r group by confidence_score order by confidence_score) x) as confidence_dist,
       (select coalesce(jsonb_object_agg(perception_channel, cnt), '{}'::jsonb)
         from (select perception_channel, count(*) cnt from r group by perception_channel order by perception_channel) x) as channel_dist,
       (select coalesce(jsonb_object_agg(rating_time_type, cnt), '{}'::jsonb)
         from (select rating_time_type, count(*) cnt from r group by rating_time_type order by rating_time_type) x) as time_type_dist,
       (select coalesce(jsonb_object_agg(rule_knowledge, cnt), '{}'::jsonb)
          from (select rule_knowledge, count(*) cnt from r group by rule_knowledge order by rule_knowledge) x) as rule_knowledge_dist,
       now()::timestamptz as computed_at
    """)
    with engine.begin() as conn:
        s = conn.execute(scene_sql, {"scene_id": str(scene_id)}).first()
        if not s:
            raise HTTPException(status_code=404, detail="Scene not found")
        row = conn.execute(agg_sql, {"scene_id": str(scene_id)}).mappings().first()

    return dict(row)

