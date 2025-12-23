import os
from dotenv import load_dotenv

load_dotenv("/opt/matchvote/api/.env")

from fastapi import FastAPI
from sqlalchemy import create_engine, text

from app.api.v1.users import router as users_router
from app.api.v1.scenes import router as scenes_router
from app.api.v1.ratings import router as ratings_router
from app.api.v1.admin import router as admin_router
from app.api.v1.matches import router as matches_router

app = FastAPI(title="MatchVote API", version="0.1.0")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://matchvote_user:But2jetMatchvote@127.0.0.1:5432/matchvote"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db/ping")
def db_ping():
    with engine.connect() as conn:
        v = conn.execute(text("select 1")).scalar()
    return {"db": v}

# v1 router
app.include_router(users_router)
app.include_router(matches_router)
app.include_router(scenes_router)
app.include_router(ratings_router)
app.include_router(admin_router)
