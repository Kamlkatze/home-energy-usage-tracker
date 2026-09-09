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
```bash
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

#### Frontend Setup
```bash
cd frontend
npm install
```

#### Start Development Services
1. Start database:
   ```bash
   docker compose up db -d
   ```

2. Start backend:
   ```bash
   cd backend
   uv run uvicorn app.main:app --reload
   ```

3. Start frontend:
   ```bash
   cd frontend
   npm run dev
   ```

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
- `GET /api/tariffs/` - List all tariff periods
- `POST /api/tariffs/` - Create a new tariff period
- `GET /api/tariffs/{id}` - Get tariff period details
- `PUT /api/tariffs/{id}` - Update tariff period
- `DELETE /api/tariffs/{id}` - Delete tariff period

## Database Schema

### Meter
- `id` (integer, primary key)
- `meter_type` (enum: gas, water_cold, water_garden, electricity_import, electricity_export, electricity_production)
- `label` (string, e.g., "Main Electricity Meter")
- `unit` (string, e.g., "kWh", "m³") - **server-derived** from `meter_type`, not client-settable: a `unit` field in a POST/PUT request body is rejected with **422 Unprocessable Entity**
- `created_at` (datetime)

### Reading
- `id` (integer, primary key)
- `meter_id` (foreign key to Meter)
- `value` (numeric, meter reading value)
- `reading_date` (date)
- `note` (string, optional)
- `created_at` (datetime)
- **Constraint**: Unique (meter_id, reading_date)

### TariffPeriod
- `id` (integer, primary key)
- `meter_id` (foreign key to Meter)
- `valid_from` (date)
- `valid_to` (date, optional, null means "valid until today")
- `price_per_unit` (numeric)
- `base_fee_monthly` (numeric, optional)
- `created_at` (datetime)
- **Constraint**: Unique (meter_id, valid_from)

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
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration with pydantic-settings
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   └── api/                 # API routes
│   ├── alembic/                 # Database migrations
│   └── pyproject.toml          # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── components/         # React components
│   │   ├── pages/             # Page components
│   │   ├── types/             # TypeScript interfaces
│   │   └── App.tsx            # Main application
│   └── package.json           # Node.js dependencies
├── docker-compose.yml         # Production Docker setup
├── docker-compose.dev.yml     # Development Docker setup
└── .env.example              # Environment variables template
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