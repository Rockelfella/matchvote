# Migrations

This project does not use Alembic. Apply SQL migrations manually in order.

Local:
1) `psql "$DATABASE_URL" -f api/migrations/20260131_sportmonks_schedules.sql`
2) `psql "$DATABASE_URL" -f api/migrations/20260131_sportmonks_inplay.sql`

Prod:
1) Run the same commands against the production database URL, in order.
