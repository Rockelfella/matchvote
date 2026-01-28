from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.deps import require_admin
from app.db import engine
from app.schemas.admin_users import AdminUserOut, AdminUserUpdate

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[AdminUserOut])
def list_users(limit: int = Query(default=200, ge=1, le=1000), offset: int = Query(default=0, ge=0)):
    sql = text("""
        select
          user_id,
          email,
          is_active,
          is_admin,
          email_verified,
          created_at
        from mv_users
        order by created_at desc
        limit :limit offset :offset
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(user_id: UUID, payload: AdminUserUpdate):
    if payload.is_active is None and payload.is_admin is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    sql = text("""
        update mv_users
        set
          is_active = coalesce(:is_active, is_active),
          is_admin = coalesce(:is_admin, is_admin)
        where user_id = :user_id
        returning
          user_id,
          email,
          is_active,
          is_admin,
          email_verified,
          created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {
            "user_id": str(user_id),
            "is_active": payload.is_active,
            "is_admin": payload.is_admin,
        }).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(row)
