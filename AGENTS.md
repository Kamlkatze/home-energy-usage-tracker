# Agent Instructions

## Hard rules
- `app/domain/` must NOT import from `app/models/`, `app/api/`, or sqlalchemy
- All money and quantity values: `Decimal`, never `float`
- Round only at output boundary: `.quantize(Decimal("0.01"), ROUND_HALF_UP)`
- Code comments in English, UI strings in German

## Commands
- Test:   `cd backend && uv run pytest`
- Lint:   `cd backend && uv run ruff check --fix && uv run mypy app/domain`
- Dev:    `docker compose -f docker-compose.dev.yml up`

## Workflow
Run tests before claiming a task is done. Do not modify files outside the
scope of the current task.
