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
  add column if not exists provider_league_id int,
  add column if not exists provider_season_id int,
  add column if not exists provider_stage_id int,
  add column if not exists provider_round_id int;

create unique index if not exists ux_matches_provider_fixture
  on referee_ratings.matches (external_provider, external_match_id);
SQL
