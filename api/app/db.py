import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://matchvote:matchvote@localhost:5432/matchvote"
)

engine = create_engine(DATABASE_URL, future=True)


def init_db():
    """
    Initialisiert / migriert die DB-Struktur idempotent.
    Wichtig: Wenn mv_users schon existiert, werden fehlende Spalten nachgezogen.
    """
    with engine.begin() as conn:

        # Extension für gen_random_uuid()
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS referee_ratings;'))

        # Tabelle minimal anlegen (falls sie noch nicht existiert)
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS mv_users (
            user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,

            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,

            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            email_verified_at TIMESTAMPTZ NULL,

            email_verify_token_hash TEXT NULL,
            email_verify_expires_at TIMESTAMPTZ NULL,

            first_login_at TIMESTAMPTZ NULL,
            last_login_at TIMESTAMPTZ NULL,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS mv_admin_dev_tokens (
            token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            issued_by UUID NOT NULL,
            target_user_id UUID NOT NULL,
            token_hash TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            requester_ip TEXT NULL,
            user_agent TEXT NULL
        );
        """))

        conn.execute(text(
            "ALTER TABLE IF EXISTS mv_admin_dev_tokens "
            "ADD COLUMN IF NOT EXISTS token_hash TEXT NULL;"
        ))

        # --- MIGRATION: fehlende Spalten nachziehen (idempotent) ---
        conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='email_verified'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='email_verified_at'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN email_verified_at TIMESTAMPTZ NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='email_verify_token_hash'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN email_verify_token_hash TEXT NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='email_verify_expires_at'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN email_verify_expires_at TIMESTAMPTZ NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='first_login_at'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN first_login_at TIMESTAMPTZ NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='mv_users' AND column_name='last_login_at'
            ) THEN
                ALTER TABLE mv_users ADD COLUMN last_login_at TIMESTAMPTZ NULL;
            END IF;
        END$$;
        """))

        # Indizes (jetzt sicher, weil Spalten garantiert vorhanden sind)
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mv_users_email ON mv_users(email);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mv_users_verify_hash ON mv_users(email_verify_token_hash);"
        ))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS referee_ratings.sportmonks_schedule_raw (
            id BIGSERIAL PRIMARY KEY,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
            payload JSONB NOT NULL
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS referee_ratings.sportmonks_schedule_fixture (
            fixture_id BIGINT PRIMARY KEY,
            starts_at TIMESTAMPTZ NULL,
            home_id BIGINT NULL,
            away_id BIGINT NULL,
            league_id BIGINT NULL,
            season_id BIGINT NULL,
            status TEXT NULL,
            venue_id BIGINT NULL,
            score_home INTEGER NULL,
            score_away INTEGER NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """))

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_starts_at "
            "ON referee_ratings.sportmonks_schedule_fixture(starts_at);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_league_id "
            "ON referee_ratings.sportmonks_schedule_fixture(league_id);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_home_id "
            "ON referee_ratings.sportmonks_schedule_fixture(home_id);"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_away_id "
            "ON referee_ratings.sportmonks_schedule_fixture(away_id);"
        ))
