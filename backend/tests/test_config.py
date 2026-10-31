"""The app version must have a single source of truth: the [project] version
in backend/pyproject.toml, exposed via app.config.settings.APP_VERSION."""

import tomllib
from pathlib import Path

from app.config import _git_commit, settings

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_app_version_matches_pyproject() -> None:
    with PYPROJECT_PATH.open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert settings.APP_VERSION == pyproject["project"]["version"]


def test_git_commit_falls_back_to_unknown_without_git(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert _git_commit() == "unknown"


def test_git_commit_env_var_takes_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GIT_COMMIT", "abc123def456")
    monkeypatch.chdir(tmp_path)
    assert _git_commit() == "abc123def456"


def test_git_commit_placeholder_unknown_treated_as_unset(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("GIT_COMMIT", "unknown")
    monkeypatch.chdir(tmp_path)
    assert _git_commit() == "unknown"
