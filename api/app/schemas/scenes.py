from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

# "Großes" MatchVote-Set an Szenen, das ihr später praktisch sicher braucht.
# Wichtig: Diese Werte müssen 1:1 auch im Postgres-Enum referee_ratings.scene_type existieren.
SceneType = Literal[
    # Schiedsrichter-Entscheidungen / Spielfortsetzungen
    "PENALTY",
    "PENALTY_REVIEW",         # VAR prüft Elfmeter
    "PENALTY_OVERTURNED",     # Elfmeter zurückgenommen
    "FREE_KICK",              # Freistoß
    "INDIRECT_FREE_KICK",     # indirekter Freistoß (selten)
    "DROP_BALL",              # Schiedsrichterball

    # Fouls / Disziplin
    "FOUL",
    "YELLOW_CARD",
    "SECOND_YELLOW",
    "RED_CARD",

    # Abseits / Tore
    "OFFSIDE",
    "GOAL",
    "OFFSIDE_GOAL",           # Tor aber Abseits
    "GOAL_DISALLOWED",        # Tor aber aus anderem Grund aberkannt
    "VAR_REVIEW",             # generischer VAR-Check
    "VAR_DECISION",           # Ergebnis eines VAR-Checks

    # Handspiel / Strafstoß-relevant
    "HANDBALL",

    # Strafraum / klare Torchance
    "DENIED_GOALSCORING_OPPORTUNITY",  # Notbremse / DOGSO

    # Weitere typische Spielereignisse
    "SUBSTITUTION",
    "INJURY_STOPPAGE",
    "TIME_WASTING",
    "DISSENT",

    # Standards / Ball im Aus
    "CORNER",
    "GOAL_KICK",
    "THROW_IN",

    # Sonstiges (für MVP hilfreich, wenn KI-Kategorisierung kommt)
    "OTHER",
]

class SceneBase(BaseModel):
    match_id: UUID
    minute: int = Field(ge=0, le=130)
    stoppage_time: Optional[int] = Field(default=None, ge=0, le=30)
    scene_type: SceneType
    description: str = Field(min_length=3, max_length=1000)

class SceneCreate(SceneBase):
    # MVP: Backend setzt created_by optional (später via Auth/JWT).
    created_by: Optional[UUID] = None

    # MVP: Release kann durch Admin erfolgen
    is_released: bool = False
    release_time: Optional[datetime] = None

class SceneOut(SceneBase):
    scene_id: UUID
    is_released: bool
    release_time: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
