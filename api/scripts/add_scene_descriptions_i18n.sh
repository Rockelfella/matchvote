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
alter table referee_ratings.scenes
  add column if not exists description_de text,
  add column if not exists description_en text;

update referee_ratings.scenes
set
  description_de = coalesce(description_de, description),
  description_en = coalesce(description_en, description)
where description is not null
  and (description_de is null or description_en is null);
SQL
