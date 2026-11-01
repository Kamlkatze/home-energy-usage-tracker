from fastapi import APIRouter

from app.config import _git_commit, settings

router = APIRouter()


@router.get("")
def get_meta() -> dict[str, str]:
    """Build metadata for the frontend footer (version + git commit)."""
    return {
        "app_version": settings.APP_VERSION,
        # Resolved live on every request so a `git pull` on the host shows up
        # without restarting the backend (the .git directory is mounted into
        # the container and re-read here).
        "git_commit": _git_commit(),
    }
