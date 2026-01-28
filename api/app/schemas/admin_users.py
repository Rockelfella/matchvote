from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    user_id: UUID
    email: str
    is_active: bool
    is_admin: bool
    email_verified: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
