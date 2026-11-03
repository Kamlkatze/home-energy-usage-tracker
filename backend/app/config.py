
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
    # 1. GIT_COMMIT env var (optional override for exotic setups; in Docker the
    #    compose files mount the host .git directory read-only into /app/.git
    #    instead, so this is normally not set).
    # 2. A .git directory found by walking up from the working directory.
    #    HEAD is read directly, no git binary needed. Works in the container
    #    (.git mounted read-only) and in native dev on the host. Because the
    #    file is read at process start, a plain restart after `git pull`
    #    picks up the new commit - no rebuild needed.
    # Never fails: the footer just shows "unknown" if nothing is resolvable.
    env_commit = os.environ.get("GIT_COMMIT", "").strip()
    if env_commit:
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
    # Session/auth settings. COOKIE_SECURE must be set to true once the app
    # is served over HTTPS (the cookie is then only sent over TLS).
    SESSION_COOKIE_NAME: str = "et_session"
    SESSION_LIFETIME_HOURS: int = 168
    COOKIE_SECURE: bool = False
    
    class Config:
        env_file = ".env"


settings = Settings()