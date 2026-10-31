
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

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


def _git_commit() -> str:
    # Resolution order:
    # 1. GIT_COMMIT env var - baked into the prod image at build time via the
    #    build arg of the same name in docker-compose.yml. The default value
    #    "unknown" is treated as unset so the fallback below can still kick in.
    # 2. A .git directory found by walking up from the working directory
    #    (native dev on the host). HEAD is read directly, no git binary needed.
    # Never fails: the footer just shows "unknown" if nothing is resolvable.
    env_commit = os.environ.get("GIT_COMMIT", "").strip()
    if env_commit and env_commit != "unknown":
        return env_commit
    try:
        current = Path.cwd()
        for candidate in (current, *current.parents):
            head = candidate / ".git" / "HEAD"
            if not head.is_file():
                continue
            ref = head.read_text().strip()
            if ref.startswith("ref:"):
                ref_file = candidate / ".git" / ref[4:].strip()
                if ref_file.is_file():
                    return ref_file.read_text().strip()[:12]
            elif ref:
                return ref[:12]
            break
    except OSError:
        pass
    return "unknown"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/energy_tracker"
    DATABASE_URL_ASYNC: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/energy_tracker"
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Home Energy Usage Tracker"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    APP_VERSION: str = _app_version()
    GIT_COMMIT: str = _git_commit()
    BACKUP_DIR: str = "/backups"
    BACKUP_KEEP_SAFETY: int = 10
    BACKUP_MAX_UPLOAD_BYTES: int = 64 * 1024 * 1024
    
    class Config:
        env_file = ".env"


settings = Settings()