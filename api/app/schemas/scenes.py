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
    "OVERALL_DECISIONS",

    # Sonstiges (für MVP hilfreich, wenn KI-Kategorisierung kommt)
    "OTHER",
]

SCENE_TYPE_LABELS = {
    "en": {
        "PENALTY": "Penalty",
        "PENALTY_REVIEW": "Penalty review",
        "PENALTY_OVERTURNED": "Penalty overturned",
        "FREE_KICK": "Free kick",
        "INDIRECT_FREE_KICK": "Indirect free kick",
        "DROP_BALL": "Drop ball",
        "FOUL": "Foul",
        "YELLOW_CARD": "Yellow card",
        "SECOND_YELLOW": "Second yellow",
        "RED_CARD": "Red card",
        "OFFSIDE": "Offside",
        "GOAL": "Goal",
        "OFFSIDE_GOAL": "Offside goal",
        "GOAL_DISALLOWED": "Goal disallowed",
        "VAR_REVIEW": "VAR review",
        "VAR_DECISION": "VAR decision",
        "HANDBALL": "Handball",
        "DENIED_GOALSCORING_OPPORTUNITY": "Denied goalscoring opportunity",
        "SUBSTITUTION": "Substitution",
        "INJURY_STOPPAGE": "Injury stoppage",
        "TIME_WASTING": "Time wasting",
        "DISSENT": "Dissent",
        "CORNER": "Corner",
        "GOAL_KICK": "Goal kick",
        "THROW_IN": "Throw-in",
        "OVERALL_DECISIONS": "Overall Decisions",
        "OTHER": "Other",
    },
    "de": {
        "PENALTY": "Elfmeter",
        "PENALTY_REVIEW": "Elfmeter-Check",
        "PENALTY_OVERTURNED": "Elfmeter zurueckgenommen",
        "FREE_KICK": "Freistoss",
        "INDIRECT_FREE_KICK": "Indirekter Freistoss",
        "DROP_BALL": "Schiedsrichterball",
        "FOUL": "Foul",
        "YELLOW_CARD": "Gelbe Karte",
        "SECOND_YELLOW": "Zweite Gelbe",
        "RED_CARD": "Rote Karte",
        "OFFSIDE": "Abseits",
        "GOAL": "Tor",
        "OFFSIDE_GOAL": "Tor im Abseits",
        "GOAL_DISALLOWED": "Tor aberkannt",
        "VAR_REVIEW": "VAR-Check",
        "VAR_DECISION": "VAR-Entscheidung",
        "HANDBALL": "Handspiel",
        "DENIED_GOALSCORING_OPPORTUNITY": "Notbremse (DOGSO)",
        "SUBSTITUTION": "Wechsel",
        "INJURY_STOPPAGE": "Verletzungspause",
        "TIME_WASTING": "Zeitspiel",
        "DISSENT": "Unsportliches Verhalten",
        "CORNER": "Ecke",
        "GOAL_KICK": "Abstoss",
        "THROW_IN": "Einwurf",
        "OVERALL_DECISIONS": "Gesamtwertung Entscheidungen",
        "OTHER": "Sonstiges",
    },
}

def get_scene_type_label(scene_type: str, lang: str) -> str:
    labels = SCENE_TYPE_LABELS.get(lang, SCENE_TYPE_LABELS["en"])
    return labels.get(scene_type, scene_type)

class SceneBase(BaseModel):
    match_id: UUID
    minute: int = Field(ge=0, le=130)
    stoppage_time: Optional[int] = Field(default=None, ge=0, le=30)
    scene_type: SceneType
    description_de: str = Field(min_length=3, max_length=1000)
    description_en: str = Field(min_length=3, max_length=1000)

class SceneCreate(SceneBase):
    # MVP: Backend setzt created_by optional (später via Auth/JWT).
    created_by: Optional[UUID] = None

    # MVP: Release kann durch Admin erfolgen
    is_released: bool = False
    release_time: Optional[datetime] = None

class SceneOut(SceneBase):
    scene_id: UUID
    scene_type_label: str
    is_released: bool
    release_time: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    description: Optional[str] = None
