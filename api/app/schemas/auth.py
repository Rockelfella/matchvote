from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
