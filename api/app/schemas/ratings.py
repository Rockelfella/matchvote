from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Enums laut DDL
PerceptionChannel = Literal["STADIUM", "TV", "STREAM", "HIGHLIGHT"]
RuleKnowledge = Literal["LOW", "MEDIUM", "HIGH"]
RatingTimeType = Literal["LIVE", "AFTER_REPLAY", "AFTER_VAR", "LATER"]


class RatingCreate(BaseModel):
    scene_id: UUID
    user_id: UUID  # MVP: ohne Auth nehmen wir user_id im Body (später aus JWT)
    decision_score: int = Field(ge=1, le=5)
    confidence_score: int = Field(ge=1, le=5)
    perception_channel: PerceptionChannel
    rule_knowledge: RuleKnowledge
    rating_time_type: RatingTimeType


class RatingOut(BaseModel):
    rating_id: UUID
    scene_id: UUID
    user_id: UUID
    decision_score: int
    confidence_score: int
    perception_channel: PerceptionChannel
    rule_knowledge: RuleKnowledge
    rating_time_type: RatingTimeType
    created_at: datetime


class SceneAggregateOut(BaseModel):
    scene_id: UUID
    rating_count: int
    avg_decision: float
    avg_confidence: float
    decision_dist: dict
    confidence_dist: dict
    channel_dist: dict
    time_type_dist: dict
    rule_knowledge_dist: dict
    computed_at: datetime
