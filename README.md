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
- `consumption` - Price per unit for consumption
- `base_fee` - Monthly base fee (optional for consumption periods)
- `feed_in` - Feed-in tariff 
- `self_consumption` - Self-consumption rate
- `metering_fee` - Metering/grid fee
- `wastewater` - Price per unit for wastewater (billed on the cold-water meter)

#### Example POST /api/tariffs/ request:
```json
{
  "meter_id": 1,
  "tariff_kind": "consumption",
  "valid_from": "2024-01-01",
  "valid_to": "2024-12-31",
  "price_per_unit": "0.3567",
  "base_fee_monthly": "15.50"
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
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

### Costs
- `GET /api/costs/?meter_id={id}&from={date}&to={date}` - Calculate the consumption cost for one meter between two dates (query parameters: `meter_id`, `from`, `to`). Returns **404** when no reading or no covering tariff period is found, **422** when `from > to` or the computed consumption is negative.

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

- `GET /api/costs/wastewater/?water_cold_meter_id={id}&water_garden_meter_id={id}&from={date}&to={date}` - Calculate the wastewater cost between two dates. Wastewater is a derived value, not a real meter: `wastewater_consumption = max(0, cold-water consumption - garden-water consumption)`, billed against a `wastewater` tariff period attached to the **cold-water meter's** id (query parameters: `water_cold_meter_id`, `water_garden_meter_id` (optional), `from`, `to`). Returns **404** when no reading or no covering wastewater tariff period is found, **422** when `from > to` or the cold-water consumption is negative.

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

#### Known limitations of the first cost calculation iteration (intentional, by design)
- **Consumption from two existing readings only**: consumption is the difference between the reading with the largest `reading_date` at or before `to` and the reading with the smallest `reading_date` at or after `from`. Readings are never interpolated or extrapolated — if either boundary reading is missing, the endpoint returns 404. A negative result (e.g. meter reset/rollover) returns 422 and is not clamped.
- **Single tariff period required**: the whole `[from, to]` range must be fully contained within exactly one `consumption` tariff period (`valid_from <= from` and `valid_to >= to` or `valid_to` null). A range spanning a tariff change returns 404 — proportional splitting across multiple periods is not implemented.
- **Fixed 30-day base fee proration**: `base_fee_total = base_fee_monthly * days_in_range / 30` with `days_in_range = (to - from).days` (inclusive-exclusive: `from` counts, `to` does not). A calendar-accurate month-length calculation is deliberately not used. A `null` `base_fee_monthly` is treated as 0.

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
- `tariff_kind` (enum: consumption, base_fee, feed_in, self_consumption, metering_fee, wastewater)
- `valid_from` (date)
- `valid_to` (date, optional, null means "open-ended - valid until today")
- `price_per_unit` (numeric)
- `base_fee_monthly` (numeric, optional)
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
│   │   │   ├── reading.py            # Reading schemas
│   │   │   └── tariff_period.py      # TariffPeriod schemas with TariffKind
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