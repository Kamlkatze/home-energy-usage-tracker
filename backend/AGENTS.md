# Backend Agent Instructions

Applies to everything under `backend/`, **in addition to** the root `AGENTS.md`
(hard rules, commands, workflow, Docker/infra learnings).

## Layout & stack

- FastAPI app in `app/`; SQLAlchemy ORM models + domain enums in `app/models/`
  (e.g. `MeterType`, `TariffKind`); Pydantic schemas in `app/schemas/`
- No `app/domain/` directory – domain logic lives in models and services
- Migrations in `alembic/` (config: `backend/alembic.ini`); tests in `tests/`
- Dev/runtime tooling via `uv` (see root AGENTS.md for commands); `uv` is **not** available
  in the prod runtime image – prod uses `/opt/venv/bin/python -m ...`

## Decimal & enum rules

- All money and quantity values: `Decimal`, never `float`
- Round only at output boundary: `.quantize(Decimal("0.01"), ROUND_HALF_UP)`
- Decimal amounts are serialized as strings in JSON to preserve precision
- SQLAlchemy enums with Python Enum classes need
  `values_callable=lambda e: [m.value for m in e]` when DB stores the value (not the name)
- Enum values in DB: lowercase (consistent with API contract), e.g. `'electricity'`, `'gas'`, `'water'`

## Database & migration rules

- Tariff overlap prevention: `excl_tariff_period_no_overlap` (EXCLUDE USING gist over
  `meter_id`, `tariff_kind`, `daterange(valid_from, valid_to, '[]')`) prevents overlaps within the
  same `(meter_id, tariff_kind)`; different tariff_kind values may overlap. The old
  `uq_meter_valid_from` UNIQUE constraint was dropped – the EXCLUDE constraint covers it (same
  valid_from always overlaps, lower bound is inclusive). Downgrade does NOT recreate it (data with
  same valid_from but different tariff_kind would violate it).
- `valid_to` semantics: nullable = open-ended (still valid today), both bounds INCLUSIVE
  (daterange `'[]'`) – adjacent periods must use `valid_to` = day before next `valid_from`
- `op.add_column` does NOT auto-create native PG enum types (unlike `op.create_table`) – create the
  enum explicitly with `.create(checkfirst=True)` and drop it in downgrade. Use
  `DROP CONSTRAINT IF EXISTS` for constraint drops so a re-upgrade after downgrade still works
- Never auto-modify data in migrations: the tariff migration checks existing rows for overlaps
  within `(meter_id, tariff_kind)` BEFORE creating the EXCLUDE constraint and aborts with a
  RuntimeError listing the conflicting rows
- Alembic conventions: all migration files use hash-based revision IDs (12-character MD5 hashes)
  in the format `{hash}_{description}.py`; the revision ID in the file header must match the hash in
  the filename. Always use `alembic revision --autogenerate -m "description"` to create new
  migrations. Validate the chain with `alembic history` and test migrations on an empty database
- Postgres enums are created lowercase in migrations; models must persist the value (not name)
  via `values_callable`

## Testing

- `conftest.py` defaults `TEST_DATABASE_URL` to the PostgreSQL test DB
  (`energy_tracker_test` on localhost:5433, `db-test` service from docker-compose.dev.yml).
  SQLite cannot enforce EXCLUDE/daterange, so tests must run on PostgreSQL
- Multi-period cost calculation: date range `[from_, to)` is inclusive-exclusive (`from_` counts,
  `to` does not); Python's date subtraction yields exclusive counting (e.g. 37 days for
  Jan 10–Feb 15, not 36)

## Domain & cost-calculation knowledge

- No fixed 30-day month convention: `_prorate_monthly()` in `app/services/cost_calculation.py`
  uses calendar-accurate month lengths (full months = 1, partial months prorated by actual days
  in that month). It replaced `_DAYS_PER_MONTH = Decimal(30)` and fixes systematic overcounting
  for periods > 30 days (365/30 = 12.167 instead of 12). Call sites: base fee in single-period,
  multi-period, multiperiod-raw, and advance-payment proration
- `metering_fee_monthly` (Messstellenbetrieb) is included in the cost total exactly like the
  Grundpreis: prorated calendar-accurately and accumulated in `_accumulate_costs()` (shared by the
  single-period, multi-period and multiperiod-raw variants, and `meter_chain_costs.py`). The
  `/api/costs/consumption-timeseries` endpoint exposes the per-point breakdown via
  `_compute_cost_fields_multiperiod_breakdown()` as `energy_cost_since_previous` /
  `base_fee_since_previous` / `metering_fee_since_previous`, which sum exactly to
  `cost_since_previous`. For feed-in/production meters the value is a Vergütung from the `feed_in`
  tariff (energy only; `base_fee_since_previous` is `null`, `metering_fee_since_previous` is
  `"0.00"`).
- Cost calculation helpers live in `app/services/`: `cost_calculation.py` (pure math),
  `cost_queries.py` (DB lookups/validation), `meter_chain_costs.py` (replacement-chain
  consumption/cost). `app/api/costs.py` keeps the routes and endpoint-specific orchestration
- Completed-year actual costs in `/api/costs/yearly-projection` are clamped to Dec 31 of the
  viewed year: the actual-cost path passes `end_bound = min(as_of_date, Dec 31 of year)` to
  `_get_boundary_readings_for_yearly_cost()` and computes `cost_end_date` from it, so readings
  from later years do not inflate consumption or base/metering fees (the boundary-reading +
  day-proration + `_compute_cost_fields_multiperiod` method is shared with ongoing years – do
  not fork it into a separate completed-year calculation). Do not remove the `end_bound` clamp:
  without it, `actual_cost_to_date` for completed years becomes grossly inflated once readings
  from a later year exist
- TariffKind simplification: standalone `base_fee` and `metering_fee` kinds were removed and merged
  into the `consumption` kind as optional `base_fee_monthly` / `metering_fee_monthly` fields
  (migration `f470c15c6414` modifies the PG enum and adds the column; no production data migration
  was needed – confirmed by maintainer). Frontend TS types and `TariffForm` updated accordingly
- `projected_meter_reading_end_of_year` (Decimal string | null) on the projection response:
  `actual_full_year` → `end_reading.value`, `insufficient_data` → `None`, linear bases →
  `start_reading.value + projected_annual`. Calculated in
  `ProjectionService.calculate_projection()`, passed through in `costs.py` when constructing
  `YearlyProjectionWithCostResponse`

## Authentication (session cookie)

- Models: `User` (`password_hash` Argon2id, `role` admin/user lowercase enum,
  `totp_secret`/`totp_enabled`, `failed_login_count`/`locked_until` lockout) and
  `AuthSession` (only the SHA-256 `token_hash` is stored; the raw token lives
  exclusively in the HttpOnly cookie `et_session`, name via
  `settings.SESSION_COOKIE_NAME`; FK `ondelete=CASCADE`)
- Security helpers in `app/security.py`: Argon2id via `argon2-cffi`,
  `validate_password_strength` (min 15 chars without MFA, 8 with MFA, max 512 –
  NIST SP 800-63B), `dummy_verify_password()` burns a real verify call for
  unknown usernames (timing-based user-enenumeration mitigation)
- Route guarding: `api_router = APIRouter(dependencies=[Depends(get_current_user)])`
  protects every business endpoint automatically; only `/health`,
  `/api/auth/login` and `/api/auth/logout` are public (`public_router`, included
  without the guard in `main.py`). New business routers must be registered on
  `api_router`, never on `public_router`
- Login (`app/api/auth.py`): all credential failures return the same generic
  German 401 message (`INVALID_CREDENTIALS`, no user enumeration). Exponential
  lockout: the Nth failed attempt (including attempts while locked) locks for
  `min(2**N, 900)` seconds → **429**; success resets the counter. TOTP-enabled
  users without a code get 401 with `detail={"message": ..., "totp_required": true}`
  so the frontend can show the code field
- Admin rules (`app/api/admin.py` + `get_current_admin`): 403 for non-admins;
  self-demotion/self-deactivation → 400; the "last active admin" check is pure
  defense-in-depth (unreachable via the API because the caller is always an
  active admin). Admin password reset deletes all sessions of the target. There
  is **no DELETE** – deactivate instead
- Tests: the `client` fixture in `conftest.py` is auto-authenticated as
  `TEST_ADMIN` (session row + cookie injected directly, no Argon2 cost per
  test); use `anon_client` for 401-assertions. Beware: httpx keeps same-name
  cookies as **separate jar entries** when attributes differ – tests that
  exercise login/logout cookie replacement must use `anon_client`
- `app/seed_admin.py` creates ADMIN-role users from the CLI, bypassing auth by
  design (local shell access dominates app auth); duplicate username and
  password policy are enforced

## Resolved pitfalls (history, don't re-introduce)

- Enum double-create bug: do not call `meter_type_enum.create()` explicitly when
  `op.create_table` already creates it
- Serialization bug: missing `values_callable` stored enum names instead of lowercase values
- Missing config files that broke builds before: `backend/alembic.ini`, `backend/.dockerignore`
