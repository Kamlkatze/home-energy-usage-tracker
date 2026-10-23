# Agent Instructions

Entry point for AI coding agents working on this repository. These rules always apply.
Scope-specific rules live in nested files and apply **in addition** to this one:

- `backend/AGENTS.md` – Python/FastAPI, SQLAlchemy, PostgreSQL, Alembic, cost calculations
- `frontend/AGENTS.md` – React 19/TypeScript, Vite, Recharts, ESLint, frontend containers

**When working inside `backend/` or `frontend/`, read that directory's `AGENTS.md` first.**

## Hard rules (repo-wide)

- Code comments in English, UI strings in German
- All money and quantity values: `Decimal`, never `float`; Decimal amounts are serialized as
  strings in JSON to preserve precision (rounding rules: see `backend/AGENTS.md`)
- If a fix does not work after two attempts, stop and report the problem instead of trying
  further variations
- Never weaken or skip a test to make the suite pass. If a requirement cannot be met, report it
  as FAILED, not as "minor issue". Fix failing tests rather than skipping them.
  Example: Fixed skipped test `test_calculate_costs_multiple_periods_different_base_fee_monthly`
  by correcting calculation errors.
- Do not silently substitute a technology for the one that was requested
  (e.g. SQLite instead of PostgreSQL) – ask or report instead
- Do not modify files outside the scope of the current task, except for infrastructure/config
  files (AGENTS.md, README) when updating documentation

## Commands

- Test:    `cd backend && uv run --extra dev pytest` (needs the `db-test` container from
  docker-compose.dev.yml on port 5433; default TEST_DATABASE_URL is PostgreSQL there – tests
  requiring the EXCLUDE constraint FAIL on SQLite, by design)
- FE test: `cd frontend && npm run test` (Vitest, 137 tests: 17 route smoke tests + 55 focused
  component tests in `src/test/*.test.tsx` + 65 unit tests for API layer/hooks in
  `src/test/*.test.ts`)
- Lint:    `cd backend && uv run --extra dev ruff check --fix && uv run --extra dev mypy app/models`
- FE lint: `cd frontend && npm run lint` (ESLint 9 flat config; exits 1 if any warning –
  target is **0 errors**, currently 38 known warnings)
- Dev:     `docker compose -f docker-compose.dev.yml up`
- Prod:    `docker compose up -d --build` (uses docker-compose.yml, mounts `./backend/app:/app/app`)
- DB console: `podman exec -it home-energy-usage-tracker_db_1 psql -U postgres -d energy_tracker`

## Workflow

1. Run tests before claiming a task is done (if tests exist)
2. Run lint/typecheck on the relevant files (models for mypy, whole backend for ruff)
3. `docker compose up -d --build` for full prod stack after changes that affect images
4. For model changes only (app/ is mounted in prod), `docker compose restart backend` is sufficient
5. After any model change (`app/models/`), regenerate the ERD:
   `cd backend && uv sync --extra dev && uv run python ../scripts/generate_erd.py --readme ../README.md --update-readme`
   – commit the updated `README.md`, `backend/docs/er-diagram.png` and `backend/docs/er-diagram.md`
   alongside the model change
6. Do not modify files outside the scope of the current task (see Hard rules)

## Architecture facts

- Monorepo: FastAPI + SQLAlchemy + PostgreSQL backend (`backend/`), React 19 + Vite frontend (`frontend/`)
- App version: single source of truth is `[project] version` in `backend/pyproject.toml`, exposed
  via `settings.APP_VERSION` (`importlib.metadata`). To change it: bump the field, run
  `cd backend && uv lock`, rebuild. Never set `APP_VERSION` in `.env`
- No `app/domain/` directory – domain logic is in `app/models/` (ORM) and `app/schemas/` (Pydantic)
- Migrations run automatically in prod via `/opt/venv/bin/python -m alembic upgrade head && ...`
  in docker-compose.yml
- Frontend: prod served by nginx on host port **3500** (mapping `3500:80`), API proxied under `/api`;
  dev via Dockerfile.dev on port 3000 (vite), native `npm run dev` uses 5173
- Uses podman (rootless) by default with `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`

## Docker & infrastructure learnings

1. Fixed Docker SIGTERM handling: replaced `&&` with `exec` to ensure uvicorn receives SIGTERM
   directly (PID 1)
2. Fixed prod backend command: uses `/opt/venv/bin/python -m` instead of `uv run`
   (uv not in runtime image)
3. Added healthcheck to development database container
4. Standardized Dockerfile naming: `frontend/Dockerfile` (production), `frontend/Dockerfile.dev`
   (development), `backend/Dockerfile`
5. Environment variable structure: centralized root `.env` with database credentials
   (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) used by both docker-compose.yml and
   docker-compose.dev.yml via `${VARNAME:-default}` substitution. `DATABASE_URL` and
   `DATABASE_URL_ASYNC` are constructed from these credentials in the Compose files
6. Backup/Restore UI (`/backup-restore`): backend image installs `postgresql-client` (trixie →
   v17 ≥ server 16; pg_dump must never be older than the server). Safety dumps go to
   `./.dockerdata/backups` (mounted as `/backups`); nginx needs `client_max_body_size` for
   restore uploads. pg_dump ≥17 emits `SET transaction_timeout = 0;` which PG16 servers reject –
   the restore strips it before `psql`. `DROP SCHEMA public` must run against the **target**
   database, the maintenance connection (`postgres` db) is only for `pg_terminate_backend`
7. nginx resolves a static `proxy_pass http://backend:8000` at startup: after
   `docker compose up -d --force-recreate backend` the frontend gets stale IPs (502) until
   `docker compose restart frontend`
8. Dev and prod compose shared the frontend image tag, so a dev `up` (podman-compose builds
   all services with `build:`) rebuilt it from `Dockerfile.dev` (vite, no nginx) and later prod
   recreates ran the wrong image (port 3500 resets). Fixed with distinct tags
   `home-energy-usage-tracker_frontend:prod` / `:dev` in the compose files
