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
# Run tests (38 passing, 2 intentional failures for constraint validation)
uv run --extra dev pytest

# Run linting
uv run --extra dev ruff check --fix
uv run --extra dev mypy app/models

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

## Testing

The backend includes comprehensive tests for all API endpoints. See [tests/README.md](tests/README.md) for detailed information.

```bash
# Run all tests with PostgreSQL (recommended)
docker compose -f ../docker-compose.dev.yml up -d db-test
TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/energy_tracker_test" \
  uv run --extra dev pytest

# Run all tests with SQLite (fallback)
uv run --extra dev pytest

# Run specific test files
uv run --extra dev pytest tests/test_meters.py
uv run --extra dev pytest tests/test_readings.py
uv run --extra dev pytest tests/test_tariff_periods.py

# Run with verbose output
uv run --extra dev pytest -v
```

**Test Coverage:**
- 40 total tests (all passing after integrity error handler fix)
- CRUD operations for meters, readings, and tariff periods
- Database constraint validation (foreign keys, uniqueness)
- API error handling and status codes (409 Conflict for constraint violations)
- Decimal serialization as strings