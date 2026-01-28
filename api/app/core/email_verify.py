import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def utcnow():
    return datetime.now(timezone.utc)


def generate_code() -> str:
    # 6-stelliger numerischer Code
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def expires_at(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)


def verification_ttl_minutes() -> int:
    return int(os.getenv("EMAIL_VERIFY_TTL_MINUTES", "15"))
