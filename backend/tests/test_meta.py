"""The /api/meta endpoint must expose the version (single source of truth:
pyproject.toml) and the git commit used by the frontend footer."""

import tomllib
from pathlib import Path

from app.config import settings

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_meta_returns_app_version_and_git_commit(client) -> None:
    response = client.get("/api/meta")

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"] == settings.APP_VERSION
    assert body["git_commit"] == settings.GIT_COMMIT

    with PYPROJECT_PATH.open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert body["app_version"] == pyproject["project"]["version"]
