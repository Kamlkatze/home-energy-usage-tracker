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

## Development Commands

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

## API Documentation

- Swagger UI: http://localhost:8000/docs (when docs enabled)
- ReDoc: http://localhost:8000/redoc

## Important Notes

- Database migrations run automatically in production via Docker Compose
- SQLAlchemy enums must use `values_callable=lambda e: [m.value for m in e]` to persist values (not names)
- All monetary values use `Decimal` and serialize as strings in JSON