"""The app version must have a single source of truth: the [project] version
in backend/pyproject.toml, exposed via app.config.settings.APP_VERSION."""

import tomllib
from pathlib import Path

from app.config import settings

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_app_version_matches_pyproject() -> None:
    with PYPROJECT_PATH.open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert settings.APP_VERSION == pyproject["project"]["version"]
