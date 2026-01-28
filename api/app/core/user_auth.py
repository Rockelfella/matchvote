from fastapi import Header, HTTPException
from sqlalchemy import text
from uuid import UUID

from app.core.security import decode_token
from app.db import engine

def require_user(authorization: str = Header(default="")) -> str:
    """
    Erwartet: Authorization: Bearer <token>
    Gibt user_id (sub) zurück.
    MVP-Quelle der Wahrheit: mv_users
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        uid = UUID(str(user_id))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT user_id, is_active FROM mv_users WHERE user_id = :uid"),
            {"uid": str(uid)},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    if not row.get("is_active", False):
        raise HTTPException(status_code=403, detail="User blocked")

    return str(uid)
