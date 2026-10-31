
from importlib.metadata import PackageNotFoundError, version

from pydantic_settings import BaseSettings


def _app_version() -> str:
    # Single source of truth: the [project] version in backend/pyproject.toml,
    # read from the installed distribution metadata. To change the app version,
    # bump that field (and rebuild/restart the backend) - do not set APP_VERSION
    # via .env. Fallback only for exotic setups without an installed project.
    try:
        return version("home-energy-tracker")
    except PackageNotFoundError:
        return "0.0.0+unknown"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/energy_tracker"
    DATABASE_URL_ASYNC: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/energy_tracker"
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Home Energy Usage Tracker"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    APP_VERSION: str = _app_version()
    BACKUP_DIR: str = "/backups"
    BACKUP_KEEP_SAFETY: int = 10
    BACKUP_MAX_UPLOAD_BYTES: int = 64 * 1024 * 1024
    
    class Config:
        env_file = ".env"


settings = Settings()