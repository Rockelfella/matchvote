from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal, Optional

LeagueCode = Literal["BL1", "BL2"]

class MatchBase(BaseModel):
    league: LeagueCode
    season: str = Field(min_length=3, max_length=20)
    match_date: datetime
    team_home: str = Field(min_length=2, max_length=100)
    team_away: str = Field(min_length=2, max_length=100)
    matchday_number: Optional[int] = Field(default=None, ge=1, le=60)
    matchday_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    matchday_name_en: Optional[str] = Field(default=None, min_length=1, max_length=100)

class MatchCreate(MatchBase):
    pass

class MatchOut(MatchBase):
    match_id: UUID
