# Home Energy Usage Tracker

A simple, local application for tracking electricity, gas, and water consumption in your household.

## Features

- **Track multiple meters**: Gas, cold/garden water (m³), electricity import/export/production (kWh) — the unit is derived automatically from the meter type
- **Record readings**: Simple form to add meter readings with dates and optional notes
- **Visualize consumption**: Line charts showing usage trends over time
- **Tariff management**: Track price per unit and base fees for different periods
- **Local deployment**: All data stays on your machine, no cloud services
- **No authentication**: Single-user, local operation only

## Tech Stack

### Backend
- **Python 3.11** with FastAPI
- **SQLAlchemy 2.0** with mapped_column syntax
- **PostgreSQL 16** database
- **Pydantic v2** for data validation
- **Alembic** for database migrations
- **uv** as package manager

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **shadcn/ui** for UI components
- **Recharts** for data visualization
- **Tailwind CSS** for styling

### Deployment
- **Docker Compose** with 3 services
- **PostgreSQL** database container
- **FastAPI** backend container
- **React** frontend container

## Getting Started

### Prerequisites
- Docker and Docker Compose
- (Optional) Node.js 18+ and Python 3.11+ for local development

### Quick Start with Docker

1. Clone the repository:
   ```bash
   git clone https://codeberg.org/Kamlkatze/home-energy-usage-tracker.git
   cd home-energy-usage-tracker
   ```

2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

3. Start all services:
   ```bash
   docker compose up -d
   ```

4. Access the application:
    - Frontend: http://localhost:3000
    - Backend API: http://localhost:8000
    - API Documentation: http://localhost:8000/docs

### Environment Configuration

The application uses a centralized `.env` file for configuration. When you copy `.env.example` to `.env`, you can customize these settings:

**Database Configuration:**
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=energy_tracker
POSTGRES_DB_TEST=energy_tracker_test  # for development/testing
```

**Network Configuration:**
```bash
DATABASE_HOST=localhost  # for native development (outside Docker)
DATABASE_PORT=5432
```

**Backend Configuration:**
```bash
API_V1_PREFIX=/api
PROJECT_NAME=Home Energy Usage Tracker
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

**Frontend Configuration (native development only):**
```bash
VITE_API_URL=http://localhost:8000  # only used outside Docker
```

**How it works:**
- Docker Compose files use `${VARNAME:-default}` substitution to load values from `.env`
- Database URLs (`DATABASE_URL`, `DATABASE_URL_ASYNC`) are automatically constructed from the credentials
- In production, `VITE_API_URL` is hardcoded to `/api` for nginx proxy routing
- In development, `VITE_API_URL` is empty for relative API calls through Vite proxy

### Native Development (Without Docker)

If you prefer to run services directly without Docker:

1. **Setup Database:**
   ```bash
   docker compose up db -d  # or use a locally installed PostgreSQL
   ```

2. **Setup Backend:**
   ```bash
   cd backend
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Setup Frontend:**
   ```bash
   cd frontend
   npm install
   ```

4. **Start Services:**
   ```bash
   # In terminal 1: Backend
   cd backend
   uv run uvicorn app.main:app --reload

   # In terminal 2: Frontend
   cd frontend
   npm run dev
   ```

5. **Access:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

**Note:** The `.env` file must have `DATABASE_HOST=localhost` and `VITE_API_URL=http://localhost:8000` for native development.

### Local Development with Docker

For full Docker development (hot-reload for both frontend and backend):

1. Start development stack:
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

2. Access:
   - Frontend: http://localhost:3000 (Vite dev server with hot reload)
   - Backend: http://localhost:8000/docs (FastAPI with auto-reload)

**Key differences in development setup:**
- Frontend: Vite dev server on port 3000 (not nginx)
  - Backend: Auto-reload enabled for code changes
  - Database: Healthcheck ensures backend waits for ready DB
  - Volumes: Code is mounted for live editing
  - Proxy Configuration:
    - Docker dev: API calls go through Vite proxy to `backend:8000`
    - Native dev: API calls go directly to `localhost:8000` (no Vite proxy)
    - Production: API calls go through nginx proxy to `backend:8000`

#### Backend Setup

### Stopping the Stacks

#### Dev Stack (docker-compose.dev.yml)

The Dev Stack includes these containers:
- `home-energy-usage-tracker_frontend_1` - Frontend development server (Vite)
- `home-energy-usage-tracker_backend_1` - Backend FastAPI server with hot-reload
- `home-energy-usage-tracker_db_1` - PostgreSQL main database
- `home-energy-usage-tracker_db-test_1` - PostgreSQL test database

**Stop the Dev Stack:**

```bash
# Stop and remove all Dev Stack containers
docker compose -f docker-compose.dev.yml down

# Stop containers without removing (for faster restart)
docker compose -f docker-compose.dev.yml stop
```

#### Prod Stack (docker-compose.yml)

The Prod Stack includes these containers:
- `home-energy-usage-tracker_frontend_1` - Frontend production build (nginx)
- `home-energy-usage-tracker_backend_1` - Backend production (uvicorn)
- `home-energy-usage-tracker_db_1` - PostgreSQL main database

**Stop the Prod Stack:**

```bash
# Stop and remove all Prod Stack containers
docker compose down

# Stop containers without removing
docker compose stop
```

**⚠️ Data Loss Warning:** `docker compose down` **removes containers but keeps volumes**. `docker compose down -v` removes volumes and all data!

#### General Commands

```bash
# Show container status
docker compose -f docker-compose.dev.yml ps
docker compose ps

# View logs of all containers
docker compose -f docker-compose.dev.yml logs

# Follow logs (Ctrl+C to stop)
docker compose -f docker-compose.dev.yml logs -f

# Show all containers for this app
docker ps -a --filter name=home-energy-usage-tracker
```

For troubleshooting and advanced shutdown options, see the complete documentation in [DOCKER_SHUTDOWN.md](DOCKER_SHUTDOWN.md).

## API Endpoints

### Meters
- `GET /api/meters/types` - List all meter types with German label and fixed unit. Example response:
  ```json
  [
    { "value": "gas", "label": "Gas", "unit": "m³" },
    { "value": "water_cold", "label": "Kaltwasser", "unit": "m³" },
    { "value": "water_garden", "label": "Gartenwasser", "unit": "m³" },
    { "value": "electricity_import", "label": "Strom Bezug", "unit": "kWh" },
    { "value": "electricity_export", "label": "Strom Einspeisung", "unit": "kWh" },
    { "value": "electricity_production", "label": "Strom Erzeugung", "unit": "kWh" }
  ]
  ```
- `GET /api/meters/` - List all meters
- `POST /api/meters/` - Create a new meter
- `GET /api/meters/{id}` - Get meter details
- `PUT /api/meters/{id}` - Update meter
- `DELETE /api/meters/{id}` - Delete meter
- `GET /api/meters/{id}/readings` - Get readings for a meter

### Readings
- `GET /api/readings/` - List all readings
- `POST /api/readings/` - Create a new reading
- `GET /api/readings/{id}` - Get reading details
- `PUT /api/readings/{id}` - Update reading
- `DELETE /api/readings/{id}` - Delete reading

### Tariff Periods
- `GET /api/tariffs/` - List all tariff periods (optional query parameter: `tariff_kind`)
- `POST /api/tariffs/` - Create a new tariff period (tariff_kind defaults to "consumption" if omitted)
- `GET /api/tariffs/{id}` - Get tariff period details
- `PUT /api/tariffs/{id}` - Update tariff period
- `DELETE /api/tariffs/{id}` - Delete tariff period

#### TariffKind Values
- `consumption` - Price per unit for consumption (may include optional `base_fee_monthly` and `metering_fee_monthly`)
- `feed_in` - Feed-in tariff 
- `self_consumption` - Self-consumption rate
- `wastewater` - Price per unit for wastewater (billed on the cold-water meter)

Note: Previously separate `base_fee` and `metering_fee` tariff kinds have been merged into the `consumption` tariff kind as optional monthly fee fields.

#### Example POST /api/tariffs/ request:
```json
{
  "meter_id": 1,
  "tariff_kind": "consumption",
  "valid_from": "2024-01-01",
  "valid_to": "2024-12-31",
  "price_per_unit": "0.3567",
  "base_fee_monthly": "15.50",
  "metering_fee_monthly": "5.80"
}
```

#### Example GET /api/tariffs/?tariff_kind=consumption response:
```json
[
  {
    "id": 1,
    "meter_id": 1,
    "tariff_kind": "consumption",
    "valid_from": "2024-01-01",
    "valid_to": "2024-12-31",
    "price_per_unit": "0.3567",
    "base_fee_monthly": "15.50",
    "metering_fee_monthly": "5.80",
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

### Costs
- `GET /api/costs/?meter_id={id}&from={date}&to={date}` - Calculate the consumption cost for one meter between two dates (query parameters: `meter_id`, `from`, `to`). Returns **404** when no reading or no covering tariff period is found, **422** when `from > to` or the computed consumption is negative.

**Multi-period support:** If the date range spans multiple tariff periods, consumption is allocated proportionally by days in each overlapping period. The `price_per_unit` field in the response shows the first period's price for backward compatibility; the total cost correctly accounts for all periods.

#### Example GET /api/costs/?meter_id=1&from=2024-01-10&to=2024-03-10 response:
```json
{
  "meter_id": 1,
  "from_date": "2024-01-10",
  "to_date": "2024-03-10",
  "consumption": "150.500",
  "unit": "kWh",
  "price_per_unit": "0.35490",
  "base_fee_total": "25.00",
  "total_cost": "78.41"
}
```

- `GET /api/costs/wastewater/?water_cold_meter_id={id}&water_garden_meter_id={id}&from={date}&to={date}` - Calculate the wastewater cost between two dates. Wastewater is a derived value, not a real meter: `wastewater_consumption = max(0, cold-water consumption - garden-water consumption)`, billed against a `wastewater` tariff period attached to the **cold-water meter's** id (query parameters: `water_cold_meter_id`, `water_garden_meter_id` (optional), `from`, `to`). Returns **404** when no reading or no covering wastewater tariff period is found, **422** when `from > to` or the cold-water consumption is negative. Supports multiple tariff periods like the main cost endpoint.

#### Garden meter omitted vs. garden meter without readings (important distinction)
- **`water_garden_meter_id` omitted entirely**: treated as "no garden meter installed". `garden_consumption = 0` and the entire cold-water consumption counts as wastewater. No garden readings are required. `water_garden_meter_id` is `null` in the response.
- **`water_garden_meter_id` provided**: the garden meter's start/end readings are looked up with the exact same rule as the cold meter. If the garden meter has **no readings in the range**, the endpoint returns **404** ("Kein Zählerstand im angegebenen Zeitraum gefunden.") — the client explicitly claimed this meter is relevant, so silently treating it as 0 would be wrong.
- A garden consumption exceeding the cold consumption is a data quality issue that is not validated here; `wastewater_consumption` is simply floored at 0.

#### Example GET /api/costs/wastewater/?water_cold_meter_id=1&water_garden_meter_id=2&from=2024-01-10&to=2024-03-10 response:
```json
{
  "water_cold_meter_id": 1,
  "water_garden_meter_id": 2,
  "from_date": "2024-01-10",
  "to_date": "2024-03-10",
  "cold_consumption": "150.500",
  "garden_consumption": "59.500",
  "wastewater_consumption": "91.000",
  "unit": "m³",
  "price_per_unit": "2.10000",
  "base_fee_total": "12.00",
  "total_cost": "203.10"
}
```

### Yearly Projection with Cost
- `GET /api/costs/yearly-projection?meter_id={id}&year={year}&as_of_date={date}` - Combine annual consumption projection with cost calculation. The `as_of_date` parameter is optional, defaults to server date (datetime.now(UTC).date()). Returns **200 OK** even with insufficient data or missing tariff, **404** if meter not found, **422** for invalid year (outside 2000-2100 range).

**Calculation Logic:**
1. **Projection**: Uses the same logic as `/api/meters/{id}/projection` to get projected annual consumption
2. **Active tariff**: Finds the consumption tariff active on `as_of_date` for the meter
3. **Actual cost**: Calculates cost from Jan 1 of `year` to `as_of_date` using existing cost calculation logic
4. **Projected cost**: Estimates annual cost using projected consumption and active tariff's rates

**Edge cases:**
- No active tariff → `projected_annual_cost = null` with explanatory message
- Insufficient data for projection → `projected_annual_cost = null` (projection basis will be "insufficient_data")
- Multiple tariff periods historically → correctly picks the one active on `as_of_date`
- Gas meter: consumption (m³) is converted to kWh via `gas_z_zahl` × `gas_brennwert` before cost calculation, for both actual and projected costs; a tariff lacking these fields → cost fields `null` with explanatory message (200)
- Actual cost unavailable (no tariff covering the period, negative consumption, missing gas factors) → `actual_cost_to_date = null` with explanatory message. If the projected path fails too, both reasons are combined into the single `message` field (deduplicated, space-separated)

#### Example GET /api/costs/yearly-projection?meter_id=1&year=2025&as_of_date=2025-06-01 response:
```json
{
  "meter_id": 1,
  "year": 2025,
  "unit": "kWh",
  "as_of_date": "2025-06-01",
  "actual_consumption_to_date": "250.500",
  "projected_annual_consumption": "601.447",
  "basis": "linear_from_prev_year_end",
  "actual_cost_to_date": "92.35",
  "projected_annual_cost": "221.89",
  "message": null
}
```

#### Example no active tariff response:
```json
{
  "meter_id": 1,
  "year": 2025,
  "unit": "kWh",
  "as_of_date": "2025-06-01",
  "actual_consumption_to_date": "250.500",
  "projected_annual_consumption": "601.447",
  "basis": "linear_from_prev_year_end",
  "actual_cost_to_date": null,
  "projected_annual_cost": null,
  "message": "Kein gültiger Tarif für diesen Zeitraum gefunden. Kein aktiver Tarif für dieses Datum gefunden."
}
```
> The `message` combines the actual-cost failure (no tariff for Jan 1 – as_of_date) and the projected-cost failure (no active tariff) into one deduplicated, space-separated string.

#### Example insufficient data response:
```json
{
  "meter_id": 1,
  "year": 2025,
  "unit": "kWh",
  "as_of_date": "2025-06-01",
  "actual_consumption_to_date": null,
  "projected_annual_consumption": null,
  "basis": "insufficient_data",
  "actual_cost_to_date": null,
  "projected_annual_cost": null,
  "message": "Nicht genügend Zählerstände im Jahr 2025 vorhanden, um eine Hochrechnung zu erstellen."
}
```

**Calculation Logic:**
- **Year completed** (year < as_of_date.year): Actual consumption = end.value - start.value (real yearly consumption)
- **Year ongoing** (year >= as_of_date.year): Linear projection = (actual consumption / elapsed days) * 365
- **Insufficient data**: When start/end readings missing or start >= end

**Start point determination:**
1. Preference: Reading exactly on December 31st of previous year
2. Fallback: First reading in the target year

#### Example GET /api/meters/1/projection?year=2025&as_of_date=2025-06-01 response (ongoing year):
```json
{
  "meter_id": 1,
  "year": 2025,
  "unit": "kWh",
  "actual_consumption_to_date": "250.500",
  "days_elapsed": 152,
  "projected_annual_consumption": "601.447",
  "basis": "linear_from_prev_year_end",
  "message": null
}
```

#### Example GET /api/meters/1/projection?year=2024 response (completed year):
```json
{
  "meter_id": 1,
  "year": 2024,
  "unit": "kWh",
  "actual_consumption_to_date": "850.250",
  "days_elapsed": 366,
  "projected_annual_consumption": "850.250",
  "basis": "actual_full_year",
  "message": null
}
```

#### Example insufficient data response:
```json
{
  "meter_id": 1,
  "year": 2024,
  "unit": "kWh",
  "actual_consumption_to_date": null,
  "days_elapsed": null,
  "projected_annual_consumption": null,
  "basis": "insufficient_data",
  "message": "Nicht genügend Zählerstände im Jahr 2024 vorhanden, um eine Hochrechnung zu erstellen."
}
```

**Basis values:**
- `"linear_from_prev_year_end"` - Start reading from December 31st of previous year
- `"linear_from_first_reading_of_year"` - Start reading from first reading in target year (fallback)
- `"actual_full_year"` - Year completed, actual consumption is final
- `"insufficient_data"` - Not enough readings for calculation

**Known limitations:**
- Uses only two boundary points (start/end) for linear projection, no regression over multiple intermediate values
- Does not account for seasonal consumption patterns
- Negative consumption values (meter rollover) are calculated as-is, not validated or clamped

## Database Schema

### Meter
- `id` (integer, primary key)
- `meter_type` (enum: electricity_import, electricity_export, electricity_production, gas, water_cold, water_garden)
- `label` (string, e.g., "Main Electricity Meter")
- `meter_number` (string, optional, e.g., "1EMH0012345678")
- `unit` (string, e.g., "kWh", "m³") - **server-derived** from `meter_type`, not client-settable: a `unit` field in a POST/PUT request body is rejected with **422 Unprocessable Entity**
- `created_at` (datetime)

### Reading
- `id` (integer, primary key)
- `meter_id` (foreign key to Meter)
- `value` (numeric, meter reading value)
- `reading_date` (date)
- `note` (string, optional)
- `created_at` (datetime)
- **Constraint**: Unique (meter_id, reading_date) - prevents duplicate readings on the same date

### TariffPeriod
- `id` (integer, primary key)
- `meter_id` (foreign key to Meter)
- `tariff_kind` (enum: consumption, feed_in, self_consumption, wastewater)
- `valid_from` (date)
- `valid_to` (date, optional, null means "open-ended - valid until today")
- `price_per_unit` (numeric)
- `base_fee_monthly` (numeric, optional, only for consumption tariff kind)
- `metering_fee_monthly` (numeric, optional, only for consumption tariff kind)
- `created_at` (datetime)
- **Constraint**: EXCLUDE USING gist (meter_id WITH =, tariff_kind WITH =, daterange(valid_from, valid_to, '[]') WITH &&)
  - Prevents overlapping periods within same (meter_id, tariff_kind)
  - Different tariff_kind values may overlap in time (e.g., consumption price and feed-in tariff can be valid simultaneously)
  - Both bounds inclusive: adjacent periods must use valid_to = day before next valid_from

## Development Commands

### Backend
```bash
# Run tests
 cd backend && uv run --extra dev pytest

 # Run linting
 cd backend && uv run --extra dev ruff check --fix && uv run --extra dev mypy app/models

 # Create migration
 cd backend && uv run alembic revision --autogenerate -m "description"

 # Apply migrations
 cd backend && uv run alembic upgrade head
```

### Frontend
```bash
# Run development server
cd frontend && npm run dev

# Build for production
cd frontend && npm run build

# Run linting
cd frontend && npm run lint
```

## Project Structure

```
home-energy-usage-tracker/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py           # Router registration
│   │   │   ├── costs.py              # Cost calculation endpoint for a date range
│   │   │   ├── deps.py               # Dependency injection (database session)
│   │   │   ├── meters.py             # CRUD endpoints for meters
│   │   │   ├── projections.py        # Projection endpoints for annual consumption
│   │   │   ├── readings.py           # CRUD endpoints for readings
│   │   │   └── tariff_periods.py     # CRUD endpoints for tariff periods
│   │   ├── models/
│   │   │   ├── __init__.py           # Exports all SQLAlchemy ORM models
│   │   │   ├── base.py               # Base model with id and timestamp mixin
│   │   │   ├── meter.py              # Meter ORM model with MeterType enum
│   │   │   ├── reading.py            # Reading ORM model
│   │   │   └── tariff_period.py      # TariffPeriod ORM model with TariffKind enum
│   │   ├── schemas/
│   │   │   ├── __init__.py           # Exports all Pydantic schemas
│   │   │   ├── cost.py               # Cost calculation response schema
│   │   │   ├── meter.py              # Meter schemas (Create, Update, Response)
│   │   │   ├── projection.py         # Projection response schema
│   │   │   ├── reading.py            # Reading schemas
│   │   │   ├── tariff_period.py      # TariffPeriod schemas with TariffKind
│   │   │   └── yearly_projection_cost.py # Yearly projection with cost response schema
│   │   ├── services/
│   │   │   └── projection.py         # Business logic for projection calculations
│   │   ├── __init__.py
│   │   ├── config.py                 # Configuration with pydantic-settings
│   │   ├── database.py               # SQLAlchemy engine and session factory
│   │   └── main.py                   # FastAPI application with middleware
│   ├── alembic/                       # Database migrations
│   ├── tests/                         # Backend tests
│   ├── pyproject.toml                # Python dependencies (uv)
│   ├── uv.lock                       # Locked dependencies
│   ├── .dockerignore
│   ├── .ruff_cache/                   # Linting cache
│   ├── .mypy_cache/                   # Type checking cache
│   └── Dockerfile                    # Production backend image
├── frontend/
│   ├── src/
│   │   ├── api/                      # API client
│   │   ├── components/               # React components
│   │   ├── components/ui/            # shadcn/ui components
│   │   ├── pages/                    # Page components
│   │   ├── types/                    # TypeScript interfaces
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── lib/                      # Utility functions
│   │   ├── App.tsx                   # Main application
│   │   └── main.tsx                  # React entry point
│   ├── dist/                         # Production build output
│   ├── node_modules/                 # Node.js dependencies
│   ├── nginx.conf                    # Nginx configuration (production)
│   ├── Dockerfile                    # Production frontend image (nginx)
│   ├── Dockerfile.dev                # Development frontend image (Vite)
│   ├── package.json                  # Node.js dependencies
│   ├── package-lock.json             # Locked dependencies
│   ├── tailwind.config.js            # Tailwind CSS configuration
│   ├── postcss.config.js             # PostCSS configuration
│   └── vite.config.ts                # Vite configuration
├── docker-compose.yml                # Production Docker setup (3 services)
├── docker-compose.dev.yml            # Development Docker setup (4 services with test DB)
├── .env.example                      # Environment variables template
├── AGENTS.md                         # Agent instructions for this project
└── README.md                         # This file
```

## Security Note

This application is designed for **local, single-user operation only**. It does not include:
- User authentication
- Role-based access control
- HTTPS (in local deployment)
- Rate limiting
- Input sanitization beyond basic validation

For production use with multiple users or internet exposure, additional security measures are required.

## Troubleshooting

### Environment Variable Issues

If services fail to connect or use incorrect database URLs:

1. **Check `.env` file exists:** Make sure `.env.example` was copied to `.env`
2. **Verify Docker Compose substitution:** 
   - Production: `docker compose config` shows resolved environment variables
   - Development: `docker compose -f docker-compose.dev.yml config`
3. **Database connection issues:**
   - Docker containers: URLs use `db` hostname (e.g., `postgresql://postgres:postgres@db:5432/energy_tracker`)
   - Native development: URLs use `localhost` hostname (matches `.env` file)
   - Ensure `DATABASE_HOST` is `localhost` for native dev, `db` for Docker

### Docker Container Hangs on Stop

If containers hang during shutdown with `SIGTERM failed to stop container ... resorting to SIGKILL`:
- Fixed: Backend uses `exec` to make uvicorn PID 1 for clean SIGTERM handling
- Fixed: Frontend uses `exec` for nginx (production) and npm (development)  
- Check: Both `docker-compose.yml` and `docker-compose.dev.yml` use `exec` in backend command
- Check: Dockerfiles use `exec` in CMD for frontend services
- Works with: Production (nginx proxy) and Development (hot-reload) setups
- Containers now stop within Docker/Podman timeout (usually 10s)

### Database Migration Issues

If you encounter `type "metertype" already exists` errors:
- The migration creates the PostgreSQL enum type automatically with the `meters` table
- If you see duplicate type creation errors, check that the migration doesn't create the enum both explicitly and implicitly
- To reset: `docker compose down --volumes` (⚠️ **deletes all data**)

### Podman-Specific Issues

This project works with both Docker and Podman. On Linux with Podman:

- Containers may be managed via systemd: `systemctl --user status podman-compose@home-energy-usage-tracker.service`
- If containers hang, check podman logs: `podman logs <container_name>`
- For rootful podman, you may need `sudo` for socket access

### API Endpoints Return 500 with Enum Errors

If POST requests fail with `invalid input value for enum metertype: "ELECTRICITY"`:
- SQLAlchemy persists enum member **names** by default (e.g., `ELECTRICITY`)
- The database stores **values** (`electricity`)
- Fix: Add `values_callable=lambda e: [m.value for m in e]` to SQLAlchemy Enum columns

### Frontend Build Issues

If TypeScript errors appear during frontend build:
- Ensure `frontend/src/vite-env.d.ts` exists with `/// <reference types="vite/client" />`
- Check for missing dependencies: `cd frontend && npm install`

## Backup & Restore

### Data Backup
To export your energy tracking data (schema is created via Alembic on the target system):

```bash
# Find your database container name
podman ps | grep postgres

# Export data only (schema comes from Alembic on the target system)
podman exec <db-container> pg_dump -U postgres -d energy_tracker \
  --data-only --column-inserts > energy_data_backup.sql
```

### Data Restore
To import data on the target system (after `alembic upgrade head` has run there):

```bash
# Find your database container name on the target system
podman ps | grep postgres

# Import the backup
cat energy_data_backup.sql | podman exec -i <db-container> \
  psql -U postgres -d energy_tracker
```

**Note**: This exports only data, not schema. The schema must be created separately via Alembic migrations (`alembic upgrade head`).

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request