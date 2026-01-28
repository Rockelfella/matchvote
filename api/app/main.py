import hashlib
from datetime import datetime, timezone


from fastapi import Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text


# DB
from app.db import engine
try:
    from app.db import init_db
except Exception:
    init_db = None

# Router (bestehend, unverändert)
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.scenes import router as scenes_router
from app.api.v1.ratings import router as ratings_router
from app.api.v1.admin import admin_router
from app.api.v1.admin_scenes import router as admin_scenes_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_matches import router as admin_matches_router
from app.api.v1.admin_sportmonks import router as admin_sportmonks_router
from app.api.v1.matches import router as matches_router
from app.api.v1.me import router as me_router
from app.api.v1.admin_dev import router as admin_dev_router
from app.core.application import app
from app.core import settings
from app.core.sportmonks import init_sportmonks_client
from app.core.deps import require_openapi_dev_token


@app.on_event("startup")
def on_startup():
    settings.validate_settings()
    if callable(init_db):
        init_db()
    if settings.SPORTMONKS_ENABLED:
        init_sportmonks_client()


@app.get("/db/ping")
def db_ping():
    with engine.connect() as conn:
        v = conn.execute(text("select 1")).scalar()
    return {"db": v}


@app.get("/admin/openapi.json", include_in_schema=False, dependencies=[Depends(require_openapi_dev_token)])
def admin_openapi():
    return JSONResponse(app.openapi(), headers={"Cache-Control": "no-store"})


# =========================================================
# EMAIL VERIFY LINK ENDPOINT (klassisch, robust)
# =========================================================
@app.get("/auth/verify-link")
def verify_link(token: str, request: Request):
    if not token or len(token) < 20:
        raise HTTPException(status_code=400, detail="Invalid token")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT user_id, email_verified, email_verify_expires_at
            FROM mv_users
            WHERE email_verify_token_hash = :h
        """), {"h": token_hash}).mappings().first()

        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        if not row["email_verified"]:
            exp = row["email_verify_expires_at"]
            if not exp or exp < now:
                raise HTTPException(status_code=400, detail="Invalid or expired token")

            conn.execute(text("""
                UPDATE mv_users
                SET email_verified = TRUE,
                    email_verified_at = NOW(),
                    is_active = TRUE,
                    email_verify_token_hash = NULL,
                    email_verify_expires_at = NULL
                WHERE user_id = :uid
            """), {"uid": str(row["user_id"])})

    # Browser → HTML
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return HTMLResponse("""
        <!doctype html>
        <html lang="de">
        <head>
          <meta charset="utf-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1"/>
          <title>MatchVote – Verified</title>
          <style>
            :root { color-scheme: dark; }
            body {
              margin:0;
              font-family: system-ui,Segoe UI,Roboto,Arial,sans-serif;
              background:#0b0f14;
              color:#e7eef7;
            }
            .wrap {
              max-width:720px;
              margin:0 auto;
              padding:40px 18px;
            }
            .card {
              background:#0d141d;
              border:1px solid #1b2633;
              border-radius:16px;
              padding:20px;
            }
          </style>
        </head>
        <body>
          <div class="wrap">
            <div class="card">
              <h2>✅ E-Mail bestätigt</h2>
              <p>Dein MatchVote-Account ist jetzt aktiv.</p>
              <p style="opacity:.8;">Du kannst dieses Fenster schließen.</p>
            </div>
          </div>
        </body>
        </html>
        """)

    # App / API → JSON
    return {"ok": True}


# Router einbinden (unverändert)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(matches_router)
app.include_router(scenes_router)
app.include_router(ratings_router)
app.include_router(me_router)
app.include_router(admin_router)
app.include_router(admin_scenes_router)
app.include_router(admin_users_router)
app.include_router(admin_matches_router)
app.include_router(admin_sportmonks_router)
app.include_router(admin_dev_router)
