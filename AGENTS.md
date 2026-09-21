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
5. After any model change (`app/models/`), regenerate the ERD: `cd backend && uv sync --extra dev && uv run python ../scripts/generate_erd.py --readme ../README.md --update-readme` – commit the updated `README.md`, `backend/docs/er-diagram.png` and `backend/docs/er-diagram.md` alongside the model change
6. Do not modify files outside the scope of the current task, except for infrastructure/config files (AGENTS.md, README) when updating documentation

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
16. Alembic migration conventions: All migration files must use hash-based Revision IDs (12-character MD5 hashes) following the format `{hash}_{description}.py`. The revision ID in the file header must match the hash in the filename. Always use `alembic revision --autogenerate -m "description"` to create new migrations, which automatically generates proper hash IDs. Migration chain must be validated with `alembic history` and test migrations on empty database.
17. Environment variable structure: Centralized .env file with database credentials (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) used by both docker-compose.yml and docker-compose.dev.yml via ${VARNAME:-default} substitution. DATABASE_URL and DATABASE_URL_ASYNC are constructed from these credentials in Compose files
18. Multi-period cost calculation fixes: Fixed date range semantics: range `[from_, to)` is inclusive-exclusive (`from_` counts, `to` does not). Python's date subtraction yields exclusive counting. Updated all test calculations to match actual implementation (37 days for Jan 10-Feb 15, not 36). Enabled previously skipped test `test_calculate_costs_multiple_periods_different_base_fee_monthly`.
19. TariffKind simplification: Removed standalone `base_fee` and `metering_fee` tariff kinds, merged into the `consumption` tariff kind as optional `base_fee_monthly` and `metering_fee_monthly` fields. Added migration `f470c15c6414` to modify PostgreSQL enum and add column. No production data migration needed (confirmed by maintainer). Updated frontend TypeScript types and TariffForm component with improved error handling for empty meter lists.
20. Added `projected_meter_reading_end_of_year` to backend projection response (Decimal string | null) and frontend `YearlyProjection` type. Calculation in `ProjectionService.calculate_projection()`: `actual_full_year` → `end_reading.value`, `insufficient_data` → `None`, linear bases → `start_reading.value + projected_annual`. Passed through in `costs.py` when constructing `YearlyProjectionWithCostResponse`.
21. Recharts tooltip with separate `<Line data={projectionData}>` only creates hit targets at points in the primary `data` array (passed to `<LineChart>`). Fixed by merging all points into `combinedData` and using `dataKey="projectedValue"` on the projection Line instead of a separate `data` prop. The main Line uses `dataKey="value"`, the projection Line uses `dataKey="projectedValue"`.
22. Recharts custom tooltip component must be defined at **module level** (not inside render function) to avoid reference changes that cause Recharts to lose tooltip state. Pass dynamic values like `unit` as props: `<Tooltip content={<ChartTooltip unit={unit} />} />`.
23. Chart dark mode styling: XAxis/YAxis need explicit `stroke="hsl(var(--muted-foreground))"` and `tick={{ fill: 'hsl(var(--muted-foreground))' }}`. Tooltip uses `background: hsl(var(--popover))`, `color: hsl(var(--popover-foreground))`, `border: 1px solid hsl(var(--border))`. YAxis `tickFormatter` for integer ticks: `(v) => Math.round(v).toString()`.
24. Frontend unit-aware formatting: kWh values display as integers (`Math.round`), m³ values display with decimals (`toFixed(1)`). Applies to consumption cards, projection cards, EEG kWh values, readings table, and YearsOverview table. Helper functions: `formatConsumption(value, unit)` and `formatReadingValue(value, unit)` in `YearDetail.tsx`. EEG kWh values hardcoded to `toFixed(0)`.
25. Removed fixed 30-day month convention (`_DAYS_PER_MONTH = Decimal(30)`) from `costs.py` – replaced by `_prorate_monthly()` which uses calendar-accurate month lengths (full months = 1, partial months prorated by actual days in that month). Fixes systematic overcounting for periods > 30 days (e.g., 365/30 = 12.167 instead of 12). Affected 4 call sites: base fee in single-period, multi-period, multiperiod-raw, and advance payment proration. Updated all test expectations and README documentation accordingly.
26. Frontend `jsx-a11y` handling: prefer a **semantic fix** (e.g. clickable non-interactive `<div>` → real `<button type="button">`, as done for the dialog backdrop at `frontend/src/components/ui/dialog.tsx`). For shared shadcn-style `forwardRef` primitives where the property (heading content, label association) is only verifiable at the caller's call site, that's a known false positive – silence it with a single inline `// eslint-disable-next-line jsx-a11y/<rule>` (comma-separated for multiple rules) and a one-line comment explaining the association happens downstream (see `card.tsx`, `label.tsx`). Never add these rules to a global ignore file. Baseline is now clean (0 `jsx-a11y` warnings in `frontend/src`).
