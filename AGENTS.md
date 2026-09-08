# Agent Instructions

## Hard rules
- `app/models/` contains SQLAlchemy ORM models with domain enums (e.g., `MeterType`)
- All money and quantity values: `Decimal`, never `float`
- Round only at output boundary: `.quantize(Decimal("0.01"), ROUND_HALF_UP)`
- Decimal amounts are serialized as strings in JSON to preserve precision
- Code comments in English, UI strings in German
- SQLAlchemy enums with Python Enum classes need `values_callable=lambda e: [m.value for m in e]` when DB stores the value (not the name)
- Enum values in DB: lowercase (consistent with API contract), e.g., `'electricity'`, `'gas'`, `'water'`

## Commands
- Test:   `cd backend && uv run --extra dev pytest` (no tests exist yet)
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
