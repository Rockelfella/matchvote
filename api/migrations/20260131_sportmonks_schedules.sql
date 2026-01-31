-- SportMonks schedules persistence tables

CREATE SCHEMA IF NOT EXISTS referee_ratings;

CREATE TABLE IF NOT EXISTS referee_ratings.sportmonks_schedule_raw (
    id BIGSERIAL PRIMARY KEY,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL
);

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

CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_starts_at
    ON referee_ratings.sportmonks_schedule_fixture(starts_at);

CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_league_id
    ON referee_ratings.sportmonks_schedule_fixture(league_id);

CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_home_id
    ON referee_ratings.sportmonks_schedule_fixture(home_id);

CREATE INDEX IF NOT EXISTS ix_sm_schedule_fixture_away_id
    ON referee_ratings.sportmonks_schedule_fixture(away_id);
