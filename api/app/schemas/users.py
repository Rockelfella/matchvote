from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

UserStatus = Literal["active", "blocked"]


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    user_id: UUID
    email_hash: str
    is_admin: bool
    status: UserStatus
    created_at: datetime
    last_login_at: Optional[datetime] = None
