import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.deps import require_admin
from app.core.security import create_openapi_dev_token
from app.db import engine

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class DevTokenIn(BaseModel):
    user_id: UUID


def _issue_token(target_user_id: UUID, issued_by: UUID, request: Request):
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    token = create_openapi_dev_token(str(target_user_id))
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO mv_admin_dev_tokens (
                issued_by, target_user_id, token_hash, expires_at, requester_ip, user_agent
            )
            VALUES (:issued_by, :target_user_id, :token_hash, :expires_at, :ip, :ua)
        """), {
            "issued_by": str(issued_by),
            "target_user_id": str(target_user_id),
            "token_hash": token_hash,
            "expires_at": expires_at,
            "ip": getattr(request.client, "host", None),
            "ua": request.headers.get("user-agent"),
        })

    return token, expires_at


@router.get("/dev-token")
def get_dev_token(request: Request, admin_user_id: UUID = Depends(require_admin)):
    token, expires_at = _issue_token(admin_user_id, admin_user_id, request)

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return HTMLResponse(f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1"/>
          <title>OpenAPI Dev Token</title>
          <style>
            body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; padding: 20px; }}
            textarea {{ width: 100%; height: 120px; font-size: 12px; }}
          </style>
        </head>
        <body>
          <h3>OpenAPI Dev Token</h3>
          <p>Valid until: {expires_at.isoformat()}</p>
          <textarea readonly>{token}</textarea>
          <p>Use as: Authorization: Bearer &lt;token&gt;</p>
        </body>
        </html>
        """)

    return {
        "token_type": "bearer",
        "access_token": token,
        "scope": "openapi:read",
        "expires_at": expires_at.isoformat(),
        "openapi_url": "/api/admin/openapi.json",
    }


@router.post("/dev-token")
def create_dev_token(payload: DevTokenIn, request: Request, admin_user_id: UUID = Depends(require_admin)):
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT user_id, is_admin, is_active
            FROM mv_users
            WHERE user_id = :uid
        """), {"uid": str(payload.user_id)}).mappings().first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if row.get("is_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Target is not admin")
    if row.get("is_active") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Target not active")

    token, expires_at = _issue_token(payload.user_id, admin_user_id, request)
    return {
        "token_type": "bearer",
        "access_token": token,
        "scope": "openapi:read",
        "expires_at": expires_at.isoformat(),
        "openapi_url": "/api/admin/openapi.json",
    }
