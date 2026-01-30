from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import engine
from app.schemas.matches import MatchCreate, MatchOut


from fastapi import Depends
from app.core.user_auth import require_user
from app.core.matches.provider_service import get_provider as get_matches_provider

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
    dependencies=[Depends(require_user), Depends(get_matches_provider)],
)

@router.get("", response_model=List[MatchOut])
def list_matches(
    limit: int = 50,
    offset: int = 0,
    league: Optional[str] = None,
    season: Optional[str] = None,
    matchday_number: Optional[int] = None,
    matchday_name: Optional[str] = None,
    matchday_name_en: Optional[str] = None,
):
    sql = """
        select
          match_id,
          league::text as league,
          season,
          match_date,
          team_home,
          team_away,
          matchday_number,
          matchday_name,
          matchday_name_en
        from referee_ratings.matches
    """
    clauses = []
    params = {"limit": limit, "offset": offset}
    if league:
        clauses.append("league = :league")
        params["league"] = league
    if season:
        clauses.append("season = :season")
        params["season"] = season
    if matchday_number is not None:
        clauses.append("matchday_number = :matchday_number")
        params["matchday_number"] = matchday_number
    if matchday_name:
        clauses.append("matchday_name = :matchday_name")
        params["matchday_name"] = matchday_name
    if matchday_name_en:
        clauses.append("matchday_name_en = :matchday_name_en")
        params["matchday_name_en"] = matchday_name_en
    if clauses:
        sql += " where " + " and ".join(clauses)
    sql += " order by match_date desc limit :limit offset :offset"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
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
          team_away,
          matchday_number,
          matchday_name,
          matchday_name_en
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
        insert into referee_ratings.matches
          (league, season, match_date, team_home, team_away, matchday_number, matchday_name, matchday_name_en)
        values
          (:league, :season, :match_date, :team_home, :team_away, :matchday_number, :matchday_name, :matchday_name_en)
        returning
          match_id,
          league::text as league,
          season,
          match_date,
          team_home,
          team_away,
          matchday_number,
          matchday_name,
          matchday_name_en
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {
            "league": payload.league,
            "season": payload.season,
            "match_date": payload.match_date,
            "team_home": payload.team_home,
            "team_away": payload.team_away,
            "matchday_number": payload.matchday_number,
            "matchday_name": payload.matchday_name,
            "matchday_name_en": payload.matchday_name_en,
        }).mappings().first()
    return row
