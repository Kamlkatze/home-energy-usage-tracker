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


def test_meta_git_commit_resolved_live_per_request(client, monkeypatch, tmp_path) -> None:
    # The endpoint must re-resolve the commit on every request (from the
    # .git directory next to the working dir), not use the value cached in
    # settings at process start - otherwise a `git pull` on the host would
    # only show up after a backend restart.
    (tmp_path / ".git" / "refs" / "heads").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / ".git" / "refs" / "heads" / "main").write_text(
        "3a7de2de11aa4480b3b83c82e7684d1b6d21e2a3\n"
    )
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.chdir(tmp_path)

    response = client.get("/api/meta")

    assert response.status_code == 200
    assert response.json()["git_commit"] == "3a7de2de11aa"
