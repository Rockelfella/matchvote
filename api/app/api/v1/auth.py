import os
import secrets
import hashlib
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.db import engine

# Wenn vorhanden: bestehende Security nutzen (klassisch im Projekt)
try:
    from app.core.security import hash_password, verify_password, create_access_token
except Exception:
    # Minimal-Fallback (sollte i.d.R. nicht greifen, aber bricht dann nicht hart)
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    def hash_password(p: str) -> str:
        return pwd_context.hash(p or "")

    def verify_password(p: str, h: str) -> bool:
        return pwd_context.verify(p or "", h or "")

    # Ohne JWT-Lib kein Token – deshalb klarer Fehler statt "halbgarem" Login
    def create_access_token(subject: str, expires_minutes: int = 60 * 24) -> str:
        raise RuntimeError("JWT not configured (app.core.security missing)")


router = APIRouter(prefix="/auth", tags=["auth"])

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://matchvote.online")
VERIFY_TOKEN_TTL_MIN = int(os.getenv("VERIFY_TOKEN_TTL_MIN", "60"))  # 60 min


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ResendIn(BaseModel):
    email: EmailStr


def _new_verify_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _send_verification_email(to_email: str, raw_token: str) -> None:
    # SMTP (Strato) – bewusst zur Laufzeit lesen (nicht beim Import cachen)
    smtp_host = os.getenv("SMTP_HOST", "smtp.strato.de")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")  # z.B. info@matchvote.de
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user

    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP_USER/SMTP_PASSWORD not configured")

    # Wir nutzen deinen Endpoint aus main.py:
    verify_url = f"{PUBLIC_BASE_URL}/api/auth/verify-link?token={raw_token}"

    subject = "MatchVote – Bitte E-Mail bestätigen"
    text_body = (
        "Hallo!\n\n"
        "Bitte bestätige deine E-Mail-Adresse für MatchVote, indem du auf diesen Link klickst:\n\n"
        f"{verify_url}\n\n"
        f"Der Link ist {VERIFY_TOKEN_TTL_MIN} Minuten gültig.\n\n"
        "Wenn du dich nicht registriert hast, ignoriere diese Mail.\n"
    )

    html_body = f"""
    <html>
      <body style="font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif; background:#0b0f14; color:#e7eef7; padding:24px;">
        <h2 style="margin:0 0 12px 0;">MatchVote – E-Mail bestätigen</h2>
        <p>Klicke auf den Button, um deinen Account zu aktivieren:</p>
        <p style="margin:18px 0;">
          <a href="{verify_url}" style="display:inline-block; padding:10px 14px; background:#1e90ff; color:white; text-decoration:none; border-radius:10px;">
            ✅ E-Mail bestätigen
          </a>
        </p>
        <p style="opacity:.8; font-size:13px;">
          Link gültig: {VERIFY_TOKEN_TTL_MIN} Minuten<br/>
          Wenn du dich nicht registriert hast, ignoriere diese Mail.
        </p>
      </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    envelope_from = smtp_user  # Strato: Envelope-From muss auth-user sein

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
            s.login(smtp_user, smtp_password)
            s.sendmail(envelope_from, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_password)
            s.sendmail(envelope_from, [to_email], msg.as_string())


@router.post("/register", status_code=201)
def register(payload: RegisterIn):
    email = payload.email.strip().lower()
    pw_hash = hash_password(payload.password)

    raw_token = _new_verify_token()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_TOKEN_TTL_MIN)

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT user_id FROM mv_users WHERE email = :email"),
            {"email": email},
        ).mappings().first()

        if exists:
            raise HTTPException(status_code=400, detail="Email already registered")

        conn.execute(text("""
            INSERT INTO mv_users (
                email, password_hash,
                is_active, is_admin,
                email_verified, email_verified_at,
                email_verify_token_hash, email_verify_expires_at,
                created_at
            )
            VALUES (
                :email, :pw_hash,
                FALSE, FALSE,
                FALSE, NULL,
                :token_hash, :expires_at,
                NOW()
            )
        """), {
            "email": email,
            "pw_hash": pw_hash,
            "token_hash": token_hash,
            "expires_at": expires_at,
        })

    # Mail raus (nach DB-Commit)
    _send_verification_email(email, raw_token)
    return {"ok": True, "detail": "Registered. Please verify your email."}


@router.post("/resend-verification")
def resend_verification(payload: ResendIn):
    email = payload.email.strip().lower()

    raw_token = _new_verify_token()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFY_TOKEN_TTL_MIN)

    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT user_id, email_verified
            FROM mv_users
            WHERE email = :email
        """), {"email": email}).mappings().first()

        # immer "neutral" antworten (keine Email-Enumeration)
        if not row:
            return {"ok": True, "detail": "If the account exists, a mail has been sent."}

        if row.get("email_verified") is True:
            return {"ok": True, "detail": "Already verified."}

        conn.execute(text("""
            UPDATE mv_users
            SET email_verify_token_hash = :token_hash,
                email_verify_expires_at = :expires_at
            WHERE email = :email
        """), {"email": email, "token_hash": token_hash, "expires_at": expires_at})

    _send_verification_email(email, raw_token)
    return {"ok": True, "detail": "If the account exists, a mail has been sent."}


@router.post("/login")
def login(payload: LoginIn):
    email = payload.email.strip().lower()
    password = payload.password

    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT user_id, password_hash, is_active, email_verified
            FROM mv_users
            WHERE email = :email
        """), {"email": email}).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not row.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")

    if not row.get("is_active", False):
        raise HTTPException(status_code=403, detail="User not active")

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE mv_users
            SET first_login_at = COALESCE(first_login_at, NOW()),
                last_login_at = NOW()
            WHERE user_id = :user_id
        """), {"user_id": row["user_id"]})

    token = create_access_token(str(row["user_id"]))
    return {"access_token": token, "token_type": "bearer"}
