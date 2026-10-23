"""Tests for the backup/restore service and API.

The subprocess layer is injected via a fake CliRunner, so no postgresql
client binaries are required; the revision graph is read from the real
alembic files. The API tests override the service dependency with a stub.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import status
from sqlalchemy.engine import make_url

from app.config import settings
from app.main import app
from app.services.backup import (
    BackupConflictError,
    BackupExecutionError,
    BackupMeta,
    BackupService,
    CliRunner,
    DumpValidation,
    RunResult,
    build_backup_filename,
    build_meta_line,
    build_pg_dump_args,
    build_psql_restore_args,
    build_revision_graph,
    get_service,
    is_ancestor,
    parse_dump_alembic_version,
    parse_meta_header,
)

DUMP_TEMPLATE = (
    "-- BACKUP-META {{\"alembic_revision\": \"{rev}\", \"pg_version\": \"16.4\", "
    "\"created_at\": \"2026-10-23T12:00:00\", \"app_version\": \"0.1.0\"}}\n"
    "--\n"
    "-- PostgreSQL database dump\n"
    "--\n\n"
    "SET statement_timeout = 0;\n"
    "SET lock_timeout = 0;\n"
    "SET idle_in_transaction_session_timeout = 0;\n"
    "SET transaction_timeout = 0;\n"
    "SET client_encoding = 'UTF8';\n"
    "CREATE TABLE public.alembic_version (\n"
    "\tversion_num character varying(32) NOT NULL\n"
    ");\n\n"
    "COPY public.alembic_version (version_num) FROM stdin;\n"
    "{rev}\n"
    "\\.\n"
    "ALTER TABLE ONLY public.alembic_version\n"
    "    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);\n"
)


def make_dump(tmp_path: Path, revision: str) -> Path:
    path = tmp_path / "backup.sql"
    path.write_text(DUMP_TEMPLATE.format(rev=revision), encoding="utf-8")
    return path


class FakeRunner(CliRunner):
    def __init__(
        self,
        stream_chunks: list[bytes] | None = None,
        run_results: list[RunResult] | None = None,
    ) -> None:
        self.stream_chunks = stream_chunks if stream_chunks is not None else [b"dump-data"]
        self.run_results = run_results if run_results is not None else [RunResult(0, b"", b"")]
        self.run_calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.stream_calls: list[list[str]] = []
        # content of the script passed to psql -f, captured before cleanup
        self.psql_scripts: list[str] = []

    async def run(self, argv, env=None):  # type: ignore[override]
        argv = list(argv)
        self.run_calls.append((argv, env))
        if argv and argv[0] == "psql" and "-f" in argv:
            script_path = Path(argv[argv.index("-f") + 1])
            self.psql_scripts.append(script_path.read_text(encoding="utf-8"))
        index = min(len(self.run_calls) - 1, len(self.run_results) - 1)
        return self.run_results[index]

    async def stream(self, argv, env=None):  # type: ignore[override]
        self.stream_calls.append(list(argv))
        for chunk in self.stream_chunks:
            yield chunk


def _value_returning(value):
    async def _method(*_args, **_kwargs):
        return value

    return _method


FAKE_URL = make_url("postgresql://u:pw@h:5432/energy_tracker")


class _NullEngine:
    def dispose(self) -> None:
        pass


class _NullAsyncEngine:
    async def dispose(self) -> None:
        pass


@pytest.fixture(scope="module")
def alembic_head_and_graph() -> tuple[str, dict]:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    graph = build_revision_graph(script)
    roots = [rev for rev, downs in graph.items() if not downs]
    assert len(roots) == 1
    return heads[0], graph


@pytest.fixture()
def patched_backup_module_engines(monkeypatch):
    import app.services.backup as backup_module

    monkeypatch.setattr(backup_module, "engine", _NullEngine())
    monkeypatch.setattr(backup_module, "async_engine", _NullAsyncEngine())


def _make_service(monkeypatch, tmp_path, db_revision, runner=None):
    svc = BackupService(runner=runner or FakeRunner())
    monkeypatch.setattr(svc, "current_db_revision", _value_returning(db_revision))
    monkeypatch.setattr(svc, "pg_version", _value_returning("16.4"))
    monkeypatch.setattr(svc, "_db_url", lambda: FAKE_URL)
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    return svc


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_meta_line_roundtrip() -> None:
    meta = BackupMeta(
        alembic_revision="abc123",
        pg_version="16.4",
        created_at="2026-10-23T12:00:00",
        app_version="0.1.0",
    )
    line = build_meta_line(meta)
    assert line.startswith("-- BACKUP-META {")
    assert parse_meta_header(line) == meta


def test_parse_meta_header_missing_or_broken() -> None:
    assert parse_meta_header("-- just a comment\nCREATE TABLE x (id int);") is None
    assert parse_meta_header("-- BACKUP-META {not json}\n") is None
    assert parse_meta_header("-- BACKUP-META {}\n") is None


def test_parse_dump_alembic_version(tmp_path: Path) -> None:
    content = make_dump(tmp_path, "3d6f19fc27d2").read_text(encoding="utf-8")
    assert parse_dump_alembic_version(content) == "3d6f19fc27d2"
    assert parse_dump_alembic_version("CREATE TABLE x (id int);") is None


def test_build_backup_filename() -> None:
    name = build_backup_filename("3d6f19fc27d2", datetime(2026, 10, 23, tzinfo=UTC))
    assert name == "2026-10-23_3d6f19fc27d2_energy_data_backup.sql"
    name = build_backup_filename("bad/../chars", datetime(2026, 1, 2, tzinfo=UTC))
    assert "/" not in name


def test_pg_dump_args_keeps_password_out_of_argv() -> None:
    url = make_url("postgresql://joe:secret@dbhost:5432/energy_tracker")
    argv, env = build_pg_dump_args(url)
    assert argv[0] == "pg_dump"
    assert "-d" in argv and "energy_tracker" in argv
    assert "--no-owner" in argv and "--no-privileges" in argv
    assert "dbhost" in argv
    assert "secret" not in " ".join(argv)
    assert env["PGPASSWORD"] == "secret"


def test_write_cleaned_script_strips_pg17_only_set(tmp_path: Path) -> None:
    src = tmp_path / "in.sql"
    src.write_text(DUMP_TEMPLATE.format(rev="abc123"), encoding="utf-8")
    out = BackupService._write_cleaned_script(src)
    text = out.read_text(encoding="utf-8")
    assert "SET transaction_timeout" not in text
    assert "SET statement_timeout = 0;" in text
    assert "COPY public.alembic_version" in text


def test_psql_restore_args_use_on_error_stop(tmp_path: Path) -> None:
    url = make_url("postgresql://joe:secret@dbhost:5432/energy_tracker")
    argv, env = build_psql_restore_args(url, tmp_path / "dump.sql")
    assert argv[0] == "psql"
    assert "ON_ERROR_STOP=1" in " ".join(argv)
    assert "secret" not in " ".join(argv)
    assert env["PGPASSWORD"] == "secret"


def test_is_ancestor_on_real_chain(alembic_head_and_graph) -> None:
    head, graph = alembic_head_and_graph
    initial = next(rev for rev, downs in graph.items() if not downs)
    assert is_ancestor(graph, initial, head) is True
    assert is_ancestor(graph, head, initial) is False
    assert is_ancestor(graph, head, head) is True
    assert is_ancestor(graph, "doesnotexist", head) is False


# ---------------------------------------------------------------------------
# Dump validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_same_revision(monkeypatch, tmp_path, alembic_head_and_graph) -> None:
    head, _graph = alembic_head_and_graph
    svc = _make_service(monkeypatch, tmp_path, db_revision=head)
    result = await svc.validate_dump_file(make_dump(tmp_path, head))
    assert result.revision == head
    assert result.needs_upgrade is False


@pytest.mark.asyncio
async def test_validate_ancestor_triggers_upgrade(monkeypatch, tmp_path, alembic_head_and_graph) -> None:
    head, graph = alembic_head_and_graph
    initial = next(rev for rev, downs in graph.items() if not downs)
    svc = _make_service(monkeypatch, tmp_path, db_revision=head)
    result = await svc.validate_dump_file(make_dump(tmp_path, initial))
    assert result.needs_upgrade is True


@pytest.mark.asyncio
async def test_validate_unknown_revision_rejected(monkeypatch, tmp_path, alembic_head_and_graph) -> None:
    head, _graph = alembic_head_and_graph
    svc = _make_service(monkeypatch, tmp_path, db_revision=head)
    with pytest.raises(BackupConflictError, match="unbekannte"):
        await svc.validate_dump_file(make_dump(tmp_path, "ffffffffffff"))


@pytest.mark.asyncio
async def test_validate_header_content_mismatch_rejected(
    monkeypatch, tmp_path, alembic_head_and_graph
) -> None:
    head, _graph = alembic_head_and_graph
    svc = _make_service(monkeypatch, tmp_path, db_revision=head)
    path = make_dump(tmp_path, head)
    content = path.read_text(encoding="utf-8").replace(
        f'"alembic_revision": "{head}"', '"alembic_revision": "000000000000"'
    )
    path.write_text(content, encoding="utf-8")
    with pytest.raises(BackupConflictError, match="beschädigt"):
        await svc.validate_dump_file(path)


@pytest.mark.asyncio
async def test_validate_no_version_info_rejected(monkeypatch, tmp_path) -> None:
    svc = _make_service(monkeypatch, tmp_path, db_revision="3d6f19fc27d2")
    path = tmp_path / "plain.sql"
    path.write_text("CREATE TABLE public.meters (id integer);\n", encoding="utf-8")
    with pytest.raises(BackupConflictError, match="keine erkennbare"):
        await svc.validate_dump_file(path)


@pytest.mark.asyncio
async def test_create_dump_stream_prepends_meta(monkeypatch, tmp_path) -> None:
    svc = _make_service(monkeypatch, tmp_path, db_revision="rev1234")
    svc.runner = FakeRunner(stream_chunks=[b"CREATE TABLE", b" x;"])
    filename, stream = await svc.create_dump_stream()
    data = b"".join([chunk async for chunk in stream])
    assert filename == build_backup_filename("rev1234", datetime.now(UTC))
    meta = parse_meta_header(data.decode())
    assert meta is not None
    assert meta.alembic_revision == "rev1234"
    assert data.endswith(b" x;")


# ---------------------------------------------------------------------------
# Restore execution (fake runner + stubbed schema/upgrade steps)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_success(monkeypatch, tmp_path, patched_backup_module_engines) -> None:
    calls: list[str] = []
    runner = FakeRunner(stream_chunks=[b"safety-dump"])
    svc = _make_service(monkeypatch, tmp_path, db_revision="revA", runner=runner)
    monkeypatch.setattr(svc, "_reset_schema_sync", lambda maint, db: calls.append("reset"))
    monkeypatch.setattr(svc, "_upgrade_head_sync", lambda: calls.append("upgrade"))

    result = await svc.restore(
        make_dump(tmp_path, "revA"),
        DumpValidation(revision="revA", needs_upgrade=False, head_revision="revA"),
    )
    assert result["message"] == "Datenbank erfolgreich wiederhergestellt."
    assert result["upgraded_to"] == ""
    assert calls == ["reset"]
    assert runner.run_calls[0][0][0] == "psql"
    # psql must receive the cleaned script without the PG17-only SET line
    assert runner.psql_scripts
    assert "SET transaction_timeout" not in runner.psql_scripts[0]
    assert "COPY public.alembic_version" in runner.psql_scripts[0]
    assert list(tmp_path.glob("*.cleaned.sql")) == []
    safety_files = list(tmp_path.glob("safety-*.sql"))
    assert len(safety_files) == 1
    content = safety_files[0].read_bytes()
    assert content.startswith(b"-- BACKUP-META ")
    assert b"safety-dump" in content


@pytest.mark.asyncio
async def test_restore_with_upgrade(monkeypatch, tmp_path, patched_backup_module_engines) -> None:
    calls: list[str] = []
    svc = _make_service(monkeypatch, tmp_path, db_revision="revOld")
    monkeypatch.setattr(svc, "_reset_schema_sync", lambda maint, db: calls.append("reset"))
    monkeypatch.setattr(svc, "_upgrade_head_sync", lambda: calls.append("upgrade"))

    dump_path = tmp_path / "upload.sql"
    dump_path.write_text("dump", encoding="utf-8")
    result = await svc.restore(
        dump_path,
        DumpValidation(revision="revOld", needs_upgrade=True, head_revision="revNew"),
    )
    assert calls == ["reset", "upgrade"]
    assert result["upgraded_to"] == "revNew"


@pytest.mark.asyncio
async def test_restore_failure_triggers_rollback(
    monkeypatch, tmp_path, patched_backup_module_engines
) -> None:
    calls: list[str] = []
    runner = FakeRunner(
        stream_chunks=[b"safety-content"],
        run_results=[
            RunResult(1, b"", b'ERROR: syntax error at or near "CREATE"'),
            RunResult(0, b"", b""),
        ],
    )
    svc = _make_service(monkeypatch, tmp_path, db_revision="revA", runner=runner)
    monkeypatch.setattr(svc, "_reset_schema_sync", lambda maint, db: calls.append("reset"))
    monkeypatch.setattr(svc, "_upgrade_head_sync", lambda: calls.append("upgrade"))

    dump_path = tmp_path / "upload.sql"
    dump_path.write_text("broken dump", encoding="utf-8")
    with pytest.raises(BackupExecutionError, match="Wiederherstellung fehlgeschlagen") as excinfo:
        await svc.restore(
            dump_path,
            DumpValidation(revision="revA", needs_upgrade=False, head_revision="revA"),
        )
    assert "automatisch wiederhergestellt" in str(excinfo.value)
    # once before the restore, once during rollback
    assert calls == ["reset", "reset"]
    rollback_argv = runner.run_calls[1][0]
    assert any("safety-" in arg for arg in rollback_argv)


@pytest.mark.asyncio
async def test_restore_upgrade_failure_triggers_rollback(
    monkeypatch, tmp_path, patched_backup_module_engines
) -> None:
    svc = _make_service(monkeypatch, tmp_path, db_revision="revA")
    monkeypatch.setattr(svc, "_reset_schema_sync", lambda maint, db: None)

    def _fail_upgrade():
        raise RuntimeError("migration exploded")

    monkeypatch.setattr(svc, "_upgrade_head_sync", _fail_upgrade)
    with pytest.raises(BackupExecutionError, match="Sicherheits-Backup"):
        await svc.restore(
            tmp_path / "upload.sql",
            DumpValidation(revision="revA", needs_upgrade=True, head_revision="revB"),
        )


def test_prune_safety_backups(monkeypatch, tmp_path) -> None:
    for index in range(5):
        (tmp_path / f"safety-2026102312{index:02d}00_revA.sql").write_text("x")
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BACKUP_KEEP_SAFETY", 3)
    svc = BackupService(runner=FakeRunner())
    svc._prune_safety_backups()
    remaining = sorted(p.name for p in tmp_path.glob("safety-*.sql"))
    assert len(remaining) == 3
    assert remaining[-1] == "safety-20261023120400_revA.sql"


# ---------------------------------------------------------------------------
# API tests (service stubbed via dependency override)
# ---------------------------------------------------------------------------


class _StubLock:
    def __init__(self, locked: bool = False) -> None:
        self._locked = locked

    def locked(self) -> bool:
        return self._locked


class StubService:
    def __init__(self) -> None:
        self.lock = _StubLock()
        self.info = {
            "db_revision": "3d6f19fc27d2",
            "head_revision": "3d6f19fc27d2",
            "pg_version": "16.4",
            "app_version": "0.1.0",
        }
        self.dump_filename = "2026-10-23_3d6f19fc27d2_energy_data_backup.sql"
        self.validate_error: Exception | None = None
        self.restore_error: Exception | None = None
        self.validation = DumpValidation(
            revision="3d6f19fc27d2", needs_upgrade=False, head_revision="3d6f19fc27d2"
        )
        self.restore_calls: list[str] = []
        self.uploaded_bytes: bytes = b""

    async def get_info(self):
        return self.info

    async def create_dump_stream(self):
        async def gen():
            yield b"-- BACKUP-META {}\n"
            yield b"CREATE TABLE public.meters (id integer);"

        return self.dump_filename, gen()

    async def validate_dump_file(self, path):
        self.uploaded_bytes = path.read_bytes()
        if self.validate_error is not None:
            raise self.validate_error
        return self.validation

    async def restore(self, path, validation):
        if self.restore_error is not None:
            raise self.restore_error
        self.restore_calls.append(validation.revision)
        return {
            "message": "Datenbank erfolgreich wiederhergestellt.",
            "dump_revision": validation.revision,
            "upgraded_to": validation.head_revision if validation.needs_upgrade else "",
        }


@pytest.fixture()
def stub_service():
    svc = StubService()
    app.dependency_overrides[get_service] = lambda: svc
    yield svc
    app.dependency_overrides.pop(get_service, None)


def test_info_endpoint(client, stub_service) -> None:
    response = client.get("/api/backup/info")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["db_revision"] == "3d6f19fc27d2"
    assert body["head_revision"] == "3d6f19fc27d2"


def test_dump_endpoint_streams_attachment(client, stub_service) -> None:
    response = client.get("/api/backup/dump")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"] == (
        'attachment; filename="2026-10-23_3d6f19fc27d2_energy_data_backup.sql"'
    )
    assert response.content.startswith(b"-- BACKUP-META")
    assert b"CREATE TABLE public.meters" in response.content


def test_dump_endpoint_conflict_while_locked(client, stub_service) -> None:
    stub_service.lock = _StubLock(locked=True)
    response = client.get("/api/backup/dump")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "läuft bereits" in response.json()["detail"]


def _post_restore(client, filename="backup.sql", content=b"dump", confirm="true"):
    return client.post(
        "/api/backup/restore",
        files={"file": (filename, content, "application/sql")},
        data={"confirm": confirm},
    )


def test_restore_requires_confirmation(client, stub_service) -> None:
    response = _post_restore(client, confirm="false")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "bestätigt" in response.json()["detail"]


def test_restore_rejects_non_sql_filename(client, stub_service) -> None:
    response = _post_restore(client, filename="backup.zip")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert ".sql" in response.json()["detail"]


def test_restore_conflict_on_incompatible_dump(client, stub_service) -> None:
    stub_service.validate_error = BackupConflictError(
        "Der Backup wurde mit einer unbekannten Datenbankversion erstellt."
    )
    response = _post_restore(client)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "unbekannten" in response.json()["detail"]
    assert stub_service.restore_calls == []


def test_restore_forwards_upload_bytes(client, stub_service) -> None:
    _post_restore(client, content=b"-- BACKUP-META {}\nsome data")
    assert stub_service.uploaded_bytes == b"-- BACKUP-META {}\nsome data"
    assert stub_service.restore_calls == ["3d6f19fc27d2"]


def test_restore_reports_upgrade_result(client, stub_service) -> None:
    stub_service.validation = DumpValidation(
        revision="7fb51c659cf1", needs_upgrade=True, head_revision="3d6f19fc27d2"
    )
    response = _post_restore(client)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["upgraded_to"] == "3d6f19fc27d2"
    assert body["dump_revision"] == "7fb51c659cf1"


def test_restore_execution_error_is_500(client, stub_service) -> None:
    stub_service.restore_error = BackupExecutionError("Wiederherstellung fehlgeschlagen: Boom")
    response = _post_restore(client)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Wiederherstellung fehlgeschlagen" in response.json()["detail"]


def test_restore_conflict_while_locked(client, stub_service) -> None:
    stub_service.lock = _StubLock(locked=True)
    response = _post_restore(client)
    assert response.status_code == status.HTTP_409_CONFLICT
