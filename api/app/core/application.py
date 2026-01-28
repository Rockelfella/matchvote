import os

from fastapi import FastAPI

from app.core import settings


app = FastAPI(
    title="MatchVote API",
    version="0.1.0",
    root_path="/api",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health():
    token = os.environ.get("SPORTMONKS_API_TOKEN")
    return {
        "status": "ok",
        "sportmonks_enabled": settings.SPORTMONKS_ENABLED,
        "sportmonks_token_present": bool(token and token.strip()),
    }
