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

## Resolved pitfalls (history, don't re-introduce)

- Enum double-create bug: do not call `meter_type_enum.create()` explicitly when
  `op.create_table` already creates it
- Serialization bug: missing `values_callable` stored enum names instead of lowercase values
- Missing config files that broke builds before: `backend/alembic.ini`, `backend/.dockerignore`
