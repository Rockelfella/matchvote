-- SportMonks inplay persistence tables

CREATE SCHEMA IF NOT EXISTS referee_ratings;

CREATE TABLE IF NOT EXISTS referee_ratings.sportmonks_inplay_raw (
    id BIGSERIAL PRIMARY KEY,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fixture_id BIGINT NULL,
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS referee_ratings.sportmonks_inplay_state (
    fixture_id BIGINT PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NULL,
    minute INTEGER NULL,
    period TEXT NULL,
    score_home INTEGER NULL,
    score_away INTEGER NULL,
    starts_at TIMESTAMPTZ NULL,
    home_id BIGINT NULL,
    away_id BIGINT NULL,
    league_id BIGINT NULL,
    season_id BIGINT NULL
);

CREATE INDEX IF NOT EXISTS ix_sm_inplay_state_updated_at
    ON referee_ratings.sportmonks_inplay_state(updated_at);
