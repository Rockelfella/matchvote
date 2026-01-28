from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.scenes import SceneType


class VoiceSceneDraft(BaseModel):
    transcript: str
    minute: Optional[int] = Field(default=None, ge=0, le=130)
    stoppage_time: Optional[int] = Field(default=None, ge=0, le=30)
    scene_type: Optional[SceneType] = None
    description_de: str
    description_en: str
    notes: Optional[str] = None
