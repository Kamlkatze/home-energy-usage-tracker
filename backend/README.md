# Home Energy Tracker Backend

FastAPI backend for tracking home energy usage.

## Installation

**With uv:**
```bash
uv sync --extra dev  # Includes development dependencies (pytest, ruff, mypy)
```

**With pip:**
```bash
pip install -e .
```

## Running

```bash
# Development (with hot-reload)
uvicorn app.main:app --reload

# Production (via docker compose preferred)
docker compose up -d --build
```

### Development Commands

```bash
# Run tests
uv run --extra dev pytest

# Run linting
uv run --extra dev ruff check --fix
uv run --extra dev mypy app/models

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## Testing

The backend includes comprehensive tests for all API endpoints. See [tests/README.md](tests/README.md) for detailed information.

```bash
# Run all tests with PostgreSQL (required for EXCLUDE constraint tests)
docker compose -f ../docker-compose.dev.yml up -d db-test
uv run --extra dev pytest

# Run specific test files
uv run --extra dev pytest tests/test_meters.py
uv run --extra dev pytest tests/test_costs.py
uv run --extra dev pytest tests/test_meter_replacement.py

# Run with verbose output
uv run --extra dev pytest -v
```

**Test Coverage (134 tests, all passing):**
- CRUD operations for meters, readings, and tariff periods
- Database constraint validation (foreign keys, uniqueness, EXCLUDE overlap)
- Cost calculation: single tariff period, multiple tariff periods, gas m³→kWh conversion
- Cost calculation: meter replacement chain (chained consumption, tariff change within chain, negative-consumption prevention)
- Meter replacement validation: `replaces_meter_id` self-reference rejection, type mismatch rejection
- Wastewater cost calculation
- Annual consumption projection
- Yearly projection with cost
- Decimal serialization as strings

## Data Model

### Meter (`app/models/meter.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `meter_type` | enum | `gas`, `water_cold`, `water_garden`, `electricity_import`, `electricity_export`, `electricity_production` |
| `label` | string(100) | |
| `meter_number` | string(100) nullable | optional hardware serial |
| `unit` | string(20) | server-derived from `meter_type`, never client-settable |
| `replaces_meter_id` | integer nullable FK → meters.id | predecessor meter this one replaced; `ON DELETE SET NULL` |
| `created_at` | datetime | |

**Meter replacement chain:** `replaces_meter_id` links a new physical meter to the old one it replaced.
The cost and projection services follow this chain automatically when computing consumption.
Validation (enforced at API level, not DB level):
- Must reference an existing meter of the **same** `meter_type` (422 otherwise)
- Self-reference is rejected (422)

### Reading (`app/models/reading.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `meter_id` | integer FK → meters.id | CASCADE delete |
| `value` | numeric(10,3) | |
| `reading_date` | date | |
| `note` | string(500) nullable | |
| `created_at` | datetime | |

**Constraint:** `UNIQUE(meter_id, reading_date)` — no duplicate readings on the same date per meter.

### TariffPeriod (`app/models/tariff_period.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `meter_id` | integer FK → meters.id | CASCADE delete |
| `tariff_kind` | enum | `consumption`, `feed_in`, `self_consumption`, `wastewater` |
| `valid_from` | date | inclusive lower bound |
| `valid_to` | date nullable | inclusive upper bound; `null` = open-ended |
| `price_per_unit` | numeric(10,5) | |
| `base_fee_monthly` | numeric(10,2) nullable | only meaningful for `consumption` tariffs |
| `metering_fee_monthly` | numeric(10,2) nullable | only meaningful for `consumption` tariffs |
| `gas_z_zahl` | numeric(10,5) nullable | Zustandszahl; required for gas cost calculation |
| `gas_brennwert` | numeric(10,5) nullable | kWh/m³; required for gas cost calculation |
| `created_at` | datetime | |

**Constraint:** `EXCLUDE USING gist (meter_id WITH =, tariff_kind WITH =, daterange(valid_from, valid_to, '[]') WITH &&)` — overlapping periods within the same `(meter_id, tariff_kind)` are rejected. Different `tariff_kind` values may overlap.

## Cost Calculation

**`app/api/costs.py`**

### Single meter
Consumption = `end_reading.value − start_reading.value`. Base fee is prorated by days
(fixed 30-day month). Multi-period ranges allocate consumption proportionally by overlapping days.
Gas meters convert m³ → kWh per-period via `gas_z_zahl × gas_brennwert`.

### Meter replacement chain
When the requested meter has a `replaces_meter_id` (or a chain of them), the endpoint:

1. Builds the chain oldest→newest via `_build_meter_chain()`.
2. Determines the transition date between each pair of meters = first reading date of the successor.
3. Computes each meter's consumption over its own active segment (`_get_chain_consumption()`).
4. Looks up tariffs **per meter** in the chain and accumulates costs **without intermediate rounding** (`_compute_cost_fields_multiperiod_raw()`).
5. Rounds the final sum once at the output boundary (AGENTS.md rule).

This prevents negative consumption from a counter reset on the new meter and correctly
applies any tariff changes that happened during the period.

## Projection Service

**`app/services/projection.py`**

`ProjectionService.calculate_projection()` accepts an optional `chain` parameter (list of
`Meter` objects, oldest first). When provided, start/end readings are searched across the
entire chain, and consumption is summed segment-by-segment — consistent with the cost
calculation chain logic.

## Migrations

All migrations live in `alembic/versions/`. IDs are 12-character MD5 hashes.

| ID | Description |
|---|---|
| `7fb51c659cf1` | Initial migration |
| `1f8d3205b439` | Add tariff_kind and prevent overlapping tariff periods |
| `b92bea1faa8f` | Extend MeterType enum (3 → 6 specific values) |
| `504b78afc834` | Add meter_number to meters |
| `e6a6932b4c88` | Add `wastewater` to TariffKind enum |
| `f470c15c6414` | Simplify TariffKind enum; add metering_fee_monthly column |
| `c1940f40123e` | Add gas conversion fields to tariff periods |
| `12182ced0bb9` | Add replaces_meter_id to meters (self-referencing FK, ON DELETE SET NULL) |
