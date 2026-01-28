#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env at ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set in .env" >&2
  exit 1
fi

# psql expects postgresql://... and not the SQLAlchemy-style prefix.
DB_URL="$(printf '%s' "$DATABASE_URL" | sed 's/^postgresql+psycopg2:\/\//postgresql:\/\//')"

psql "$DB_URL" <<'SQL'
alter table referee_ratings.matches
  add column if not exists external_provider text,
  add column if not exists external_match_id text,
  add column if not exists status text,
  add column if not exists last_polled_at timestamptz,
  add column if not exists last_event_id bigint;

create table if not exists referee_ratings.match_events (
  provider text not null,
  fixture_id text not null,
  event_id bigint not null,
  payload jsonb not null,
  created_at timestamptz default now(),
  unique (provider, fixture_id, event_id)
);
SQL
