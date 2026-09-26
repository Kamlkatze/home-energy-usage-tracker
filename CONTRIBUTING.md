# Contributing to Home Energy Usage Tracker

Thanks for your interest in contributing! This guide covers setup, commands, and the
workflow we expect. For AI coding agents the same rules live in `AGENTS.md`
(root, `backend/`, `frontend/`) – keep both in sync when dev workflows change.

## Prerequisites

- Docker/Podman + docker-compose (podman rootless is the default here:
  `DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`)
- [uv](https://docs.astral.sh/uv/) for the backend
- Node.js 20+ and npm for the frontend

## Quickstart

1. Create a root `.env` with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   (used by both compose files via `${VARNAME:-default}`)
2. Start the dev stack: `docker compose -f docker-compose.dev.yml up`
   - frontend: http://localhost:3000 (vite), backend API: `http://backend:8000` in-container,
     `db-test` on port 5433 for the test suite
3. Prod stack: `docker compose up -d --build` (frontend served by nginx on host port **3500**)

## Commands

| What        | Backend                                             | Frontend                  |
|-------------|-----------------------------------------------------|---------------------------|
| Tests       | `cd backend && uv run --extra dev pytest`           | `cd frontend && npm run test` |
| Lint        | `cd backend && uv run --extra dev ruff check --fix && uv run --extra dev mypy app/models` | `cd frontend && npm run lint` |
| Dev server  | via dev compose                                     | `cd frontend && npm run dev` (port 5173 native) |
| Migrations  | `cd backend && uv run alembic revision --autogenerate -m "description"` | – |

Note: backend tests require the PostgreSQL `db-test` container – SQLite cannot enforce the
EXCLUDE/daterange constraints, by design.

## Code style essentials

- Code comments in English, UI strings in German (may change in future)
- All money and quantity values: `Decimal`, never `float` (serialized as strings in JSON)
- Never weaken or skip a test to make the suite pass; if a requirement cannot be met,
  report it as FAILED
- After any change to `backend/app/models/`: regenerate the ERD
  (`cd backend && uv sync --extra dev && uv run python ../scripts/generate_erd.py --readme ../README.md --update-readme`)
  and commit the updated `README.md`, `backend/docs/er-diagram.png` and `backend/docs/er-diagram.md`
- Migrations: hash-based revision IDs via `alembic revision --autogenerate`, never auto-modify
  data in migrations – abort instead (details: `backend/AGENTS.md`)

## Workflow for a change

1. Branch off `main`, keep the change scoped to the task
2. Run tests + lint (`0 errors` required; frontend currently has ~50 known warnings)
3. If images are affected: `docker compose up -d --build` and smoke-test the stack;
   model-only changes need just `docker compose restart backend` (app/ is mounted in prod)
4. Commit, push, open a pull request – describe *what* and *why*, link related issues

## Documentation map

- `README.md` – features, API endpoints, database schema, troubleshooting, backup/restore
- `backend/README.md` – data model, cost calculation, projection service, migrations
- `frontend/README.md` – pages, components, API integration, ESLint/React-19 migration notes
- `AGENTS.md` (root + nested) – rules for AI coding agents

## License & conduct

By contributing you agree that your contributions are licensed under the MIT license, and
you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
