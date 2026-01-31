# Migrations

This project does not use Alembic. Apply SQL migrations manually in order.

Local:
1) `psql "$DATABASE_URL" -f api/migrations/20260131_sportmonks_schedules.sql`

Prod:
1) Run the same command against the production database URL.
