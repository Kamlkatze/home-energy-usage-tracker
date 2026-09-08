# Home Energy Usage Tracker

A simple, local application for tracking electricity, gas, and water consumption in your household.

## Features

- **Track multiple meters**: Electricity (kWh), Gas (m³), Water (m³)
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

### Local Development

#### Backend Setup
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
- `meter_type` (enum: electricity, gas, water)
- `label` (string, e.g., "Main Electricity Meter")
- `unit` (string, e.g., "kWh", "m³")
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
cd backend && uv run pytest

# Run linting
cd backend && uv run ruff check --fix && uv run mypy app

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

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request