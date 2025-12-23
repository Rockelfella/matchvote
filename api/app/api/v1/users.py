from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.schemas.users import UserRegister, UserOut

router = APIRouter(prefix="/v1/users", tags=["Users"])


@router.post("", response_model=UserOut, status_code=201)
def register_user(payload: UserRegister):
    sql = text("""
        insert into referee_ratings.users (email_hash, password_hash)
        values (
            encode(digest(lower(trim(:email)), 'sha256'), 'hex'),
            crypt(:password, gen_salt('bf'))
        )
        returning
          user_id,
          email_hash,
          is_admin,
          status::text as status,
          created_at,
          last_login_at
    """)

    with engine.begin() as conn:
        try:
            row = conn.execute(
                sql,
                {"email": payload.email, "password": payload.password}
            ).mappings().first()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")

    return dict(row)
