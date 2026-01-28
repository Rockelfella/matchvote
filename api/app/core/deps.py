from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from uuid import UUID

from app.db import engine
from app.core.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)
openapi_bearer = HTTPBearer(auto_error=False)

def require_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UUID:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = creds.credentials

    try:
        payload = decode_token(token)
        if payload.get("typ") == "dev-openapi":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev token not allowed")
        user_id = UUID(str(payload.get("sub")))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # MVP: Auth-Quelle ist mv_users
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT user_id, is_active FROM mv_users WHERE user_id = :uid"),
            {"uid": str(user_id)},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not row.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User blocked")

    return user_id


def require_admin(user_id: UUID = Depends(require_user)) -> UUID:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT is_admin FROM mv_users WHERE user_id = :uid"),
            {"uid": str(user_id)},
        ).mappings().first()

    if not row or row.get("is_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    return user_id


def require_openapi_dev_token(
    creds: HTTPAuthorizationCredentials = Depends(openapi_bearer),
) -> dict:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("typ") != "dev-openapi":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token type")
    if payload.get("is_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    if payload.get("scope") != "openapi:read":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")
    if not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid subject")

    return payload
