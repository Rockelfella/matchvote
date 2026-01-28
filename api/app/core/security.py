import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from jose import jwt, JWTError
from passlib.context import CryptContext

# bcrypt macht in deinem Setup Ärger (72-byte / backend detection).
# PBKDF2 ist stabil, bewährt, ohne harte 72-byte Grenze.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret

def hash_password(password: str) -> str:
    return pwd_context.hash(password or "")

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password or "", password_hash)

def create_access_token(subject: str, expires_minutes: int = 60 * 24) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)

def create_openapi_dev_token(subject: str, expires_minutes: int = 60 * 24) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "is_admin": True,
        "scope": "openapi:read",
        "typ": "dev-openapi",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError("Invalid token") from e
