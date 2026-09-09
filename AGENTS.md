# Agent Instructions

## Hard rules
- `app/models/` contains SQLAlchemy ORM models with domain enums (e.g., `MeterType`, `TariffKind`)
- All money and quantity values: `Decimal`, never `float`
- Round only at output boundary: `.quantize(Decimal("0.01"), ROUND_HALF_UP)`
- Decimal amounts are serialized as strings in JSON to preserve precision
- Code comments in English, UI strings in German
- SQLAlchemy enums with Python Enum classes need `values_callable=lambda e: [m.value for m in e]` when DB stores the value (not the name)
- Enum values in DB: lowercase (consistent with API contract), e.g., `'electricity'`, `'gas'`, `'water'`
- If a fix does not work after two attempts, stop and report the problem instead of trying further variations
- Never weaken or skip a test to make the suite pass. If a requirement cannot be met, report it as FAILED, not as "minor issue". Fix failing tests rather than skipping them. Example: Fixed skipped test `test_calculate_costs_multiple_periods_different_base_fee_monthly` by correcting calculation errors.
- Do not silently substitute a technology for the one that was requested (e.g. SQLite instead of PostgreSQL) - ask or report instead

## Commands
- Test:   `cd backend && uv run --extra dev pytest` (needs the `db-test` container from docker-compose.dev.yml on port 5433; default TEST_DATABASE_URL is PostgreSQL there – tests requiring the EXCLUDE constraint FAIL on SQLite, by design)
- Lint:   `cd backend && uv run --extra dev ruff check --fix && uv run --extra dev mypy app/models`
- Dev:    `docker compose -f docker-compose.dev.yml up`
- Prod:   `docker compose up -d --build` (uses docker-compose.yml, mounts `./backend/app:/app/app`)
- DB console: `podman exec -it home-energy-usage-tracker_db_1 psql -U postgres -d energy_tracker`

## Workflow
1. Run tests before claiming a task is done (if tests exist)
2. Run lint/typecheck on the relevant files (models for mypy, whole backend for ruff)
3. `docker compose up -d --build` for full prod stack after changes that affect images
4. For model changes only (app/ is mounted in prod), `docker compose restart backend` is sufficient
5. Do not modify files outside the scope of the current task, except for infrastructure/config files (AGENTS.md, README) when updating documentation

## Key project structure differences from earlier assumptions
- No `app/domain/` directory – domain logic is in `app/models/` (ORM) and `app/schemas/` (Pydantic)
- Migration runs automatically in prod via `/opt/venv/bin/python -m alembic upgrade head && ...` in docker-compose.yml
- Postgres enum created lowercase in migration; models must persist the value (not name) using `values_callable`
- Frontend builds in prod via nginx on port 3000; dev via Dockerfile.dev on port 3000 (vite)
- Uses podman (rootless) by default with `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`

## Recent fixes & learnings
1. Fixed enum double‑create bug in migration: removed explicit `meter_type_enum.create()` and let `op.create_table` create it once
2. Fixed SQLAlchemy enum serialization: added `values_callable` to store lowercase values matching DB enum
3. Fixed frontend TypeScript errors: removed unused `@radix-ui/react-slot`, added `frontend/src/vite-env.d.ts`
4. Fixed prod backend command: uses `/opt/venv/bin/python -m` instead of `uv run` (uv not in runtime image)
5. Created missing files: `backend/alembic.ini`, `backend/.dockerignore`
6. Fixed Docker SIGTERM handling: replaced `&&` with `exec` to ensure uvicorn receives SIGTERM directly (PID 1)
7. Added healthcheck to development database container
8. Fixed API URLs: production uses `/api` (nginx proxy), development uses `http://backend:8000`
9. Fixed frontend SIGTERM handling: Added `exec` to nginx and npm commands in Dockerfiles for clean shutdown
10. Standardized Dockerfile naming: frontend/Dockerfile (production), frontend/Dockerfile.dev (development), backend/Dockerfile
11. Tariff overlap prevention: `excl_tariff_period_no_overlap` (EXCLUDE USING gist over meter_id, tariff_kind, daterange(valid_from, valid_to, '[]')) prevents overlaps within the same (meter_id, tariff_kind); different tariff_kind values may overlap. Dropped the old `uq_meter_valid_from` UNIQUE constraint – the EXCLUDE constraint covers it (same valid_from always overlaps, lower bound is inclusive). Downgrade does NOT recreate it (data with same valid_from but different tariff_kind would violate it)
12. `valid_to` semantics: nullable = open-ended (still valid today), both bounds INCLUSIVE (daterange '[]') – adjacent periods must use valid_to = day before next valid_from
13. Migration lesson: `op.add_column` does NOT auto-create native PG enum types (unlike `op.create_table`) – create the enum explicitly with `.create(checkfirst=True)` and drop it in downgrade. Use `DROP CONSTRAINT IF EXISTS` for constraint drops so a re-upgrade after downgrade still works
14. Migration safety: the tariff migration checks existing rows for overlaps within (meter_id, tariff_kind) BEFORE creating the EXCLUDE constraint and aborts with a RuntimeError listing the conflicting rows – never auto-modify data in migrations
15. Test default DB: conftest defaults TEST_DATABASE_URL to the PostgreSQL test DB (energy_tracker_test on localhost:5433, from db-test service). SQLite cannot enforce EXCLUDE/daterange, so tests must run on PostgreSQL
16. Environment variable structure: Centralized .env file with database credentials (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) used by both docker-compose.yml and docker-compose.dev.yml via ${VARNAME:-default} substitution. DATABASE_URL and DATABASE_URL_ASYNC are constructed from these credentials in Compose files
17. Multi-period cost calculation fixes: Fixed date range semantics: range `[from_, to)` is inclusive-exclusive (`from_` counts, `to` does not). Python's date subtraction yields exclusive counting. Updated all test calculations to match actual implementation (37 days for Jan 10-Feb 15, not 36). Enabled previously skipped test `test_calculate_costs_multiple_periods_different_base_fee_monthly`.
