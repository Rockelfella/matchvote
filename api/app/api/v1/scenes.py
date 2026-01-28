from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text

from app.db import engine
from app.schemas.scenes import SceneCreate, SceneOut, get_scene_type_label
from app.schemas.ratings import SceneAggregateOut

from fastapi import Depends
from app.core.user_auth import require_user

router = APIRouter(prefix="/scenes", tags=["scenes"], dependencies=[Depends(require_user)])

def _pick_lang(accept_language: Optional[str]) -> str:
    if not accept_language:
        return "en"
    for part in accept_language.split(","):
        lang = part.split(";")[0].strip().lower()
        if lang.startswith("de"):
            return "de"
        if lang.startswith("en"):
            return "en"
    return "en"

def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    row = conn.execute(text("""
        select 1
        from information_schema.columns
        where table_schema = :schema
          and table_name = :table
          and column_name = :column
        limit 1
    """), {"schema": schema, "table": table, "column": column}).first()
    return bool(row)

def _add_scene_type_label(rows, lang: str):
    return [
        {
            **row,
            "scene_type_label": get_scene_type_label(row["scene_type"], lang),
            "description": row.get("description_de"),
        }
        for row in rows
    ]

@router.get("", response_model=List[SceneOut])
def list_scenes(
    match_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
):
    if match_id:
        sql = text("""
            select
              scene_id,
              match_id,
              minute,
              stoppage_time,
              scene_type,
              description_de,
              description_en,
              is_released,
              release_time,
              created_by,
              created_at
            from referee_ratings.scenes
            where match_id = :match_id
              and scene_type != 'GOAL'
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
              description_de,
              description_en,
              is_released,
              release_time,
              created_by,
              created_at
            from referee_ratings.scenes
            where scene_type != 'GOAL'
            order by created_at desc nulls last
            limit :limit offset :offset
        """)
        params = {"limit": limit, "offset": offset}

    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, params).mappings().all()]
    return _add_scene_type_label(rows, _pick_lang(accept_language))

@router.get("/{scene_id}", response_model=SceneOut)
def get_scene(
    scene_id: UUID,
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
):
    sql = text("""
        select
          scene_id,
          match_id,
          minute,
          stoppage_time,
          scene_type,
          description_de,
          description_en,
          is_released,
          release_time,
          created_by,
          created_at
        from referee_ratings.scenes
        where scene_id = :scene_id
          and scene_type != 'GOAL'
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    result = dict(row)
    result["scene_type_label"] = get_scene_type_label(result["scene_type"], _pick_lang(accept_language))
    result["description"] = result.get("description_de")
    return result

@router.post("", response_model=SceneOut, status_code=201)
def create_scene(
    payload: SceneCreate,
    user_id: str = Depends(require_user),
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
):
    # created_by wird serverseitig aus dem JWT gesetzt
    with engine.begin() as conn:
        include_legacy = _column_exists(conn, "referee_ratings", "scenes", "description")
        if include_legacy:
            sql = text("""
                insert into referee_ratings.scenes
                  (match_id, minute, stoppage_time, scene_type, description, description_de, description_en, is_released, release_time, created_by)
                values
                  (:match_id, :minute, :stoppage_time, :scene_type, :description, :description_de, :description_en, :is_released, :release_time, :created_by)
                returning
                  scene_id,
                  match_id,
                  minute,
                  stoppage_time,
                  scene_type,
                  description_de,
                  description_en,
                  is_released,
                  release_time,
                  created_by,
                  created_at
            """)
        else:
            sql = text("""
                insert into referee_ratings.scenes
                  (match_id, minute, stoppage_time, scene_type, description_de, description_en, is_released, release_time, created_by)
                values
                  (:match_id, :minute, :stoppage_time, :scene_type, :description_de, :description_en, :is_released, :release_time, :created_by)
                returning
                  scene_id,
                  match_id,
                  minute,
                  stoppage_time,
                  scene_type,
                  description_de,
                  description_en,
                  is_released,
                  release_time,
                  created_by,
                  created_at
            """)

        # Keep legacy short description populated with the German text for iOS compatibility.
        legacy_description = payload.description_de
        row = conn.execute(sql, {
            "match_id": str(payload.match_id),
            "minute": payload.minute,
            "stoppage_time": payload.stoppage_time,
            "scene_type": payload.scene_type,
            "description": legacy_description,
            "description_de": payload.description_de,
            "description_en": payload.description_en,
            "is_released": payload.is_released,
            "release_time": payload.release_time,
            "created_by": user_id,
        }).mappings().first()
    result = dict(row)
    result["scene_type_label"] = get_scene_type_label(result["scene_type"], _pick_lang(accept_language))
    result["description"] = result.get("description_de")
    return result
@router.get("/{scene_id}/aggregate", response_model=SceneAggregateOut)
def scene_aggregate(scene_id: UUID):
    # scene exists?
    scene_sql = text("""
        select scene_id
        from referee_ratings.scenes
        where scene_id = :scene_id
          and scene_type != 'GOAL'
    """)
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
        srow = conn.execute(scene_sql, {"scene_id": str(scene_id)}).first()
        if not srow:
            raise HTTPException(status_code=404, detail="Scene not found")
        row = conn.execute(agg_sql, {"scene_id": str(scene_id)}).mappings().first()

    return dict(row)
