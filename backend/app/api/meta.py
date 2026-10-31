from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("")
def get_meta() -> dict[str, str]:
    """Build metadata for the frontend footer (version + git commit)."""
    return {
        "app_version": settings.APP_VERSION,
        "git_commit": settings.GIT_COMMIT,
    }
