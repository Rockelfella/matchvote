from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Engine
from uuid import UUID
from typing import List

from app.db import engine
from app.schemas.matches import MatchCreate, MatchOut

router = APIRouter(prefix="/v1/matches", tags=["matches"])

@router.get("", response_model=List[MatchOut])
def list_matches(limit: int = 50, offset: int = 0):
    sql = text("""
        select
          match_id,
          league::text as league,
          season,
          match_date,
          team_home,
          team_away
        from referee_ratings.matches
        order by match_date desc
        limit :limit offset :offset
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
    return rows

@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: UUID):
    sql = text("""
        select
          match_id,
          league::text as league,
          season,
          match_date,
          team_home,
          team_away
        from referee_ratings.matches
        where match_id = :match_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"match_id": str(match_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return row

@router.post("", response_model=MatchOut, status_code=201)
def create_match(payload: MatchCreate):
    sql = text("""
        insert into referee_ratings.matches (league, season, match_date, team_home, team_away)
        values (:league, :season, :match_date, :team_home, :team_away)
        returning
          match_id,
          league::text as league,
          season,
          match_date,
          team_home,
          team_away
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {
            "league": payload.league,
            "season": payload.season,
            "match_date": payload.match_date,
            "team_home": payload.team_home,
            "team_away": payload.team_away,
        }).mappings().first()
    return row
