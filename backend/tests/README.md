# Testing Strategy

## Database Testing

The test suite runs against PostgreSQL 16, matching the production database.
This ensures PostgreSQL-specific features (native enums, EXCLUDE constraints) 
are properly tested.

### Test Database Setup

Two approaches are supported:

1. **Dedicated Test Database (Recommended for development)**:
   - A `db-test` service runs in `docker-compose.dev.yml` on port 5433
   - Database URL: `postgresql://postgres:postgres@localhost:5433/energy_tracker_test`
   - Set `TEST_DATABASE_URL` environment variable to use this
   - Schema is created via Alembic migrations (not `Base.metadata.create_all()`)

2. **SQLite In-Memory (Fallback)**:
   - Used when `TEST_DATABASE_URL` is not set
   - Schema created via `Base.metadata.create_all()`
   - Doesn't test PostgreSQL-specific features

### Running Tests

```bash
# With PostgreSQL test database (recommended)
cd backend
TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/energy_tracker_test" \
  uv run --extra dev pytest

# With SQLite (fallback)
cd backend
uv run --extra dev pytest
```

### Test Isolation

- Each test runs in a transaction that's rolled back afterwards
- This keeps tests fast and independent
- The database schema is created once per test session

### Integrity Error Handling

The application has a global exception handler for `sqlalchemy.exc.IntegrityError`:
- Returns HTTP 409 Conflict instead of 500 Internal Server Error
- Maps known constraint violations to German error messages
- Never leaks SQL statements or stack traces
- Logs full exceptions server-side for debugging

Known constraint mappings:
- `uq_meter_reading_date` → "Für diesen Zähler existiert bereits ein Zählerstand an diesem Datum."
- `uq_meter_valid_from` → "Für diesen Zähler existiert bereits ein Tarifzeitraum mit diesem Startdatum."

## Why PostgreSQL for Tests?

1. **Feature Parity**: Tests PostgreSQL-specific features (enums, constraints)
2. **Migration Testing**: Alembic migrations are tested, not just model creation
3. **Real-world Behavior**: SQLite behaves differently than PostgreSQL for some operations
4. **Constraint Names**: PostgreSQL provides constraint names in error details for better error messages

## Test Data

Fixtures provide sample data for:
- Meters (electricity/gas/water)
- Readings (consumption values)
- Tariff periods (pricing periods)

Tests verify:
- CRUD operations
- Database constraints
- API error handling
- Decimal serialization as strings