from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.db import engine
from app.core.user_auth import require_user

router = APIRouter(prefix="/me", tags=["me"])


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    row = conn.execute(text("""
        select 1
        from information_schema.columns
        where table_schema = :schema
          and table_name = :table
          and column_name = :column
        limit 1
    """), {"schema": schema, "table": table, "column": column}).first()
    return bool(row)


@router.get("")
def get_me(user_id: str = Depends(require_user)):
    sql = text("""
        select
            user_id::text as user_id,
            email,
            coalesce(is_admin,false) as is_admin,
            coalesce(is_active,true) as is_active,
            first_login_at,
            last_login_at,
            created_at
        from mv_users
        where user_id = cast(:user_id as uuid)
        limit 1
    """)

    with engine.begin() as conn:
        row = conn.execute(sql, {"user_id": user_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="User disabled")

    return {
        "email": row["email"],
        "is_admin": bool(row["is_admin"]),
        "is_active": bool(row["is_active"]),
        "first_login_at": row["first_login_at"],
        "last_login_at": row["last_login_at"],
        "created_at": row["created_at"],
    }


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
    },
)
def delete_me(user_id: str = Depends(require_user)):
    with engine.begin() as conn:
        exists = conn.execute(
            text("select user_id from mv_users where user_id = cast(:user_id as uuid)"),
            {"user_id": user_id},
        ).first()
        if not exists:
            raise HTTPException(status_code=404, detail="User not found")

        if _column_exists(conn, "referee_ratings", "ratings", "user_id"):
            conn.execute(
                text("delete from referee_ratings.ratings where user_id = cast(:user_id as uuid)"),
                {"user_id": user_id},
            )

        if _column_exists(conn, "referee_ratings", "users", "user_id"):
            conn.execute(
                text("delete from referee_ratings.users where user_id = cast(:user_id as uuid)"),
                {"user_id": user_id},
            )

        if _column_exists(conn, "referee_ratings", "scenes", "created_by"):
            conn.execute(
                text("update referee_ratings.scenes set created_by = null where created_by = cast(:user_id as uuid)"),
                {"user_id": user_id},
            )

        if _column_exists(conn, "referee_ratings", "audit_log", "actor_user_id"):
            conn.execute(
                text("update referee_ratings.audit_log set actor_user_id = null where actor_user_id = cast(:user_id as uuid)"),
                {"user_id": user_id},
            )

        if _column_exists(conn, "public", "audit_log", "actor_user_id"):
            conn.execute(
                text("update public.audit_log set actor_user_id = null where actor_user_id = cast(:user_id as uuid)"),
                {"user_id": user_id},
            )

        deleted = conn.execute(
            text("delete from mv_users where user_id = cast(:user_id as uuid)"),
            {"user_id": user_id},
        )
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
