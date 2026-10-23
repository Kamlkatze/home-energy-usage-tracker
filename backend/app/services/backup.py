"""Backup/restore service: pg_dump streaming, restore with safety backup and
alembic-revision compatibility checks.

Subprocess invocation is abstracted behind a CliRunner protocol so that the
command construction, metadata parsing and revision validation can be unit
tested without the postgres client binaries being present.
"""

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from alembic import command

from ..config import settings
from ..database import async_engine, engine

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSIONS_DIR = BACKEND_ROOT / "alembic" / "versions"

META_PREFIX = "-- BACKUP-META "
META_LINE_RE = re.compile(r"^-- BACKUP-META (\{.*\})\s*$", re.MULTILINE)
# pg_dump writes the alembic_version table contents as a COPY block.
COPY_ALEMBIC_VERSION_RE = re.compile(
    r"COPY public\.alembic_version[^\n;]*FROM stdin;\n([^\n]*)\n\\\.\n"
)

SQL_FILENAME_TEMPLATE = "{date}_{revision}_energy_data_backup.sql"
# See BackupService._write_cleaned_script
UNSUPPORTED_SET_RE = re.compile(r"^SET transaction_timeout = [^;]+;\n", re.MULTILINE)


class BackupError(Exception):
    """Base error; message is shown to the user (German)."""


class BackupConflictError(BackupError):
    """The dump is not compatible with the current database/code (HTTP 409)."""


class BackupExecutionError(BackupError):
    """A dump/restore command failed at execution time (HTTP 500)."""


@dataclass
class BackupMeta:
    alembic_revision: str
    pg_version: str
    created_at: str
    app_version: str


@dataclass
class RunResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class CliRunner:
    """Protocol-ish base class; tests inject a fake implementation."""

    async def run(self, argv: Sequence[str], env: dict[str, str] | None = None) -> RunResult:
        raise NotImplementedError

    def stream(
        self, argv: Sequence[str], env: dict[str, str] | None = None
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError


class AsyncCliRunner(CliRunner):
    def _full_env(self, extra: dict[str, str] | None) -> dict[str, str]:
        env = dict(os.environ)
        if extra:
            env.update(extra)
        return env

    async def run(self, argv: Sequence[str], env: dict[str, str] | None = None) -> RunResult:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._full_env(env),
        )
        out, err = await proc.communicate()
        return RunResult(proc.returncode if proc.returncode is not None else -1, out, err)

    async def stream(
        self, argv: Sequence[str], env: dict[str, str] | None = None
    ) -> AsyncIterator[bytes]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._full_env(env),
        )
        stderr_buffer = bytearray()
        assert proc.stderr is not None
        stderr_collector = asyncio.create_task(self._drain(proc.stderr, stderr_buffer))
        try:
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
            returncode = await proc.wait()
            if returncode != 0:
                raise BackupExecutionError(
                    f"Datenbank-Programm fehlgeschlagen (Code {returncode}): "
                    f"{stderr_buffer.decode(errors='replace')[:500]}"
                )
        finally:
            if proc.returncode is None:
                proc.kill()
            await stderr_collector

    @staticmethod
    async def _drain(stream: asyncio.StreamReader, buffer: bytearray) -> None:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            buffer.extend(chunk)


# ---------------------------------------------------------------------------
# Pure helpers (no I/O) – unit testable without binaries or database
# ---------------------------------------------------------------------------


def build_meta_line(meta: BackupMeta) -> str:
    payload = json.dumps(
        {
            "alembic_revision": meta.alembic_revision,
            "pg_version": meta.pg_version,
            "created_at": meta.created_at,
            "app_version": meta.app_version,
        },
        sort_keys=True,
    )
    return f"{META_PREFIX}{payload}\n"


def parse_meta_header(content: str) -> BackupMeta | None:
    match = None
    for line in content.splitlines()[:10]:
        match = META_LINE_RE.match(line)
        if match:
            break
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    revision = payload.get("alembic_revision")
    if not isinstance(revision, str) or not revision:
        return None
    return BackupMeta(
        alembic_revision=revision,
        pg_version=str(payload.get("pg_version", "")),
        created_at=str(payload.get("created_at", "")),
        app_version=str(payload.get("app_version", "")),
    )


def parse_dump_alembic_version(content: str) -> str | None:
    match = COPY_ALEMBIC_VERSION_RE.search(content)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def build_backup_filename(revision: str, now: datetime) -> str:
    safe_revision = re.sub(r"[^A-Za-z0-9_-]", "", revision) or "unknown"
    return SQL_FILENAME_TEMPLATE.format(date=now.strftime("%Y-%m-%d"), revision=safe_revision)


def _libpq_args(url: URL) -> tuple[list[str], dict[str, str]]:
    argv = [
        "-h", str(url.host or "localhost"),
        "-p", str(url.port or 5432),
        "-U", str(url.username or "postgres"),
    ]
    env = {"PGPASSWORD": url.password or ""}
    return argv, env


def build_pg_dump_args(url: URL) -> tuple[list[str], dict[str, str]]:
    argv, env = _libpq_args(url)
    return (
        ["pg_dump", *argv, "-d", str(url.database), "--no-owner", "--no-privileges"],
        env,
    )


def build_psql_restore_args(url: URL, path: Path) -> tuple[list[str], dict[str, str]]:
    argv, env = _libpq_args(url)
    return (
        ["psql", "-v", "ON_ERROR_STOP=1", "-q", *argv, "-d", str(url.database), "-f", str(path)],
        env,
    )


def _down_revisions(down_revision: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if down_revision is None:
        return ()
    if isinstance(down_revision, str):
        return (down_revision,)
    return tuple(down_revision)


def build_revision_graph(script: ScriptDirectory) -> dict[str, tuple[str, ...]]:
    return {
        rev.revision: _down_revisions(rev.down_revision)
        for rev in script.walk_revisions()
    }


def is_ancestor(graph: Mapping[str, Sequence[str]], ancestor: str, node: str) -> bool:
    if ancestor == node:
        return True
    seen = {node}
    stack = [node]
    while stack:
        current = stack.pop()
        for down in graph.get(current, ()):
            if down == ancestor:
                return True
            if down not in seen:
                seen.add(down)
                stack.append(down)
    return False


@dataclass
class DumpValidation:
    revision: str
    needs_upgrade: bool
    head_revision: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BackupService:
    def __init__(self, runner: CliRunner | None = None) -> None:
        self.runner: CliRunner = runner or AsyncCliRunner()
        self.lock = asyncio.Lock()

    # -- database helpers (sync drivers inside worker threads) --

    @staticmethod
    def _db_url() -> URL:
        return make_url(settings.DATABASE_URL)

    def _query_scalar(self, statement: str, url: URL | None = None) -> str | None:
        target = url if url is not None else self._db_url()
        connectable = create_engine(target, pool_pre_ping=True)
        try:
            with connectable.connect() as conn:
                return conn.execute(text(statement)).scalar()
        finally:
            connectable.dispose()

    def _current_revision_sync(self) -> str | None:
        try:
            return self._query_scalar("SELECT version_num FROM alembic_version")
        except Exception:
            logger.exception("Could not read alembic_version")
            return None

    async def current_db_revision(self) -> str | None:
        return await asyncio.to_thread(self._current_revision_sync)

    async def pg_version(self) -> str:
        try:
            version = await asyncio.to_thread(self._query_scalar, "SHOW server_version")
        except Exception:  # noqa: BLE001 - info endpoint must stay usable
            return "unknown"
        return version or "unknown"

    @staticmethod
    def _alembic_config() -> AlembicConfig:
        cfg = AlembicConfig()
        cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        return cfg

    def _head_revision_sync(self) -> tuple[str, Mapping[str, Sequence[str]]]:
        script = ScriptDirectory.from_config(self._alembic_config())
        heads = script.get_heads()
        if len(heads) != 1:
            raise BackupExecutionError(
                f"Erwartet genau eine Alembic-Head-Revision, gefunden: {heads}"
            )
        return heads[0], build_revision_graph(script)

    async def head_revision_and_graph(self) -> tuple[str, Mapping[str, Sequence[str]]]:
        return await asyncio.to_thread(self._head_revision_sync)

    # -- info --

    async def get_info(self) -> dict[str, str]:
        db_revision, head = await asyncio.gather(
            self.current_db_revision(),
            self._head_only(),
        )
        return {
            "db_revision": db_revision or "",
            "head_revision": head,
            "pg_version": await self.pg_version(),
            "app_version": settings.APP_VERSION,
        }

    async def _head_only(self) -> str:
        head, _graph = await self.head_revision_and_graph()
        return head

    # -- dump --

    async def create_dump_stream(self) -> tuple[str, AsyncIterator[bytes]]:
        """Return (filename, chunk iterator). The iterator holds the service
        lock for its lifetime; the caller must pre-check ``lock.locked()``."""

        async def gen() -> AsyncIterator[bytes]:
            async with self.lock:
                revision = await self.current_db_revision() or "unknown"
                meta = BackupMeta(
                    alembic_revision=revision,
                    pg_version=await self.pg_version(),
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                    app_version=settings.APP_VERSION,
                )
                yield build_meta_line(meta).encode("utf-8")
                url = self._db_url()
                argv, env = build_pg_dump_args(url)
                async for chunk in self.runner.stream(argv, env):
                    yield chunk

        revision = await self.current_db_revision() or "unknown"
        filename = build_backup_filename(revision, datetime.now(UTC))
        return filename, gen()

    # -- validation --

    async def validate_dump_file(self, path: Path) -> DumpValidation:
        content = await asyncio.to_thread(self._read_dump_text, path)
        meta = parse_meta_header(content)
        copy_revision = parse_dump_alembic_version(content)
        if meta is None and copy_revision is None:
            raise BackupConflictError(
                "Die Datei enthält keine erkennbare Alembic-Versionsinformation. "
                "Bitte nur einen von dieser Anwendung erstellten Backup verwenden."
            )
        if meta is not None and copy_revision is not None and meta.alembic_revision != copy_revision:
            raise BackupConflictError(
                "Der Backup-Kopf und der Inhalt der Datei stimmen nicht "
                f"({meta.alembic_revision} vs. {copy_revision}). Datei ist beschädigt."
            )
        revision = copy_revision or (meta.alembic_revision if meta else "")
        head, graph = await self.head_revision_and_graph()
        db_revision = await self.current_db_revision()
        if revision == db_revision:
            return DumpValidation(revision=revision, needs_upgrade=False, head_revision=head)
        if revision == head:
            return DumpValidation(revision=revision, needs_upgrade=False, head_revision=head)
        if is_ancestor(graph, revision, head):
            return DumpValidation(revision=revision, needs_upgrade=True, head_revision=head)
        if revision not in graph:
            raise BackupConflictError(
                f"Der Backup wurde mit einer unbekannten Datenbankversion "
                f"({revision}) erstellt und passt nicht zu dieser Installation (Version {head})."
            )
        raise BackupConflictError(
            f"Der Backup-Datenbankversion ({revision}) ist neuer als die dieser "
            f"Installation ({head}). Bitte zuerst die Anwendung aktualisieren."
        )

    @staticmethod
    def _read_dump_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise BackupError(f"Datei konnte nicht gelesen werden: {exc}") from exc

    # -- restore execution --

    async def restore(self, path: Path, validation: DumpValidation) -> dict[str, str]:
        url = self._db_url()
        maint_url = url.set(database="postgres")

        async with self.lock:
            safety_path = await self._create_safety_backup(url)
            engine.dispose()
            await async_engine.dispose()
            try:
                await asyncio.to_thread(self._reset_schema_sync, maint_url, url)
                await self._run_psql(url, path)
                upgraded_to = validation.head_revision if validation.needs_upgrade else ""
                if validation.needs_upgrade:
                    await asyncio.to_thread(self._upgrade_head_sync)
            except Exception as exc:
                logger.exception("Restore failed, starting automatic rollback")
                rollback_msg = await self._rollback(maint_url, url, safety_path)
                raise BackupExecutionError(
                    f"Wiederherstellung fehlgeschlagen: {exc}. "
                    f"{rollback_msg} Sicherheits-Backup: {safety_path.name}"
                ) from exc
            finally:
                engine.dispose()
                await async_engine.dispose()
            self._prune_safety_backups()

        return {
            "message": "Datenbank erfolgreich wiederhergestellt.",
            "dump_revision": validation.revision,
            "upgraded_to": upgraded_to,
        }

    async def _create_safety_backup(self, url: URL) -> Path:
        revision = await self.current_db_revision() or "unknown"
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        name = f"safety-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{revision}.sql"
        target = backup_dir / name
        meta = BackupMeta(
            alembic_revision=revision,
            pg_version=await self.pg_version(),
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            app_version=settings.APP_VERSION,
        )
        argv, env = build_pg_dump_args(url)
        with target.open("wb") as fh:
            fh.write(build_meta_line(meta).encode("utf-8"))
            async for chunk in self.runner.stream(argv, env):
                fh.write(chunk)
        return target

    async def _run_psql(self, url: URL, path: Path) -> None:
        cleaned = await asyncio.to_thread(self._write_cleaned_script, path)
        try:
            argv, env = build_psql_restore_args(url, cleaned)
            result = await self.runner.run(argv, env)
            if result.returncode != 0:
                detail = result.stderr.decode(errors="replace")[:500]
                raise BackupExecutionError(f"psql (Code {result.returncode}): {detail}")
        finally:
            cleaned.unlink(missing_ok=True)

    @staticmethod
    def _write_cleaned_script(path: Path) -> Path:
        # pg_dump >= 17 emits "SET transaction_timeout" (a PG17-only GUC) even
        # for older servers; psql against the restore server would abort.
        content = path.read_text(encoding="utf-8", errors="replace")
        cleaned_path = path.with_name(f"{path.stem}.cleaned.sql")
        cleaned_path.write_text(UNSUPPORTED_SET_RE.sub("", content), encoding="utf-8")
        return cleaned_path

    def _reset_schema_sync(self, maint_url: URL, app_url: URL) -> None:
        db_name = str(app_url.database)
        connectable = create_engine(maint_url, isolation_level="AUTOCOMMIT")
        try:
            with connectable.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db AND pid <> pg_backend_pid()"
                    ),
                    {"db": db_name},
                )
        finally:
            connectable.dispose()
        # Drop/create on the TARGET database, not on the maintenance database.
        target = create_engine(app_url, isolation_level="AUTOCOMMIT")
        try:
            with target.connect() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
        finally:
            target.dispose()

    def _upgrade_head_sync(self) -> None:
        command.upgrade(self._alembic_config(), "head")

    async def _rollback(self, maint_url: URL, url: URL, safety_path: Path) -> str:
        try:
            await asyncio.to_thread(self._reset_schema_sync, maint_url, url)
            await self._run_psql(url, safety_path)
            engine.dispose()
            await async_engine.dispose()
            return "Die vorherige Datenbank wurde automatisch wiederhergestellt."
        except Exception:
            logger.exception("Automatic rollback failed")
            return (
                "Die automatische Wiederherstellung schlug fehl – bitte das "
                "Sicherheits-Backup manuell einspielen."
            )

    def _prune_safety_backups(self) -> None:
        backup_dir = Path(settings.BACKUP_DIR)
        try:
            files = sorted(backup_dir.glob("safety-*.sql"), reverse=True)
        except OSError:
            return
        for stale in files[settings.BACKUP_KEEP_SAFETY:]:
            try:
                stale.unlink()
            except OSError:
                logger.warning("Could not prune backup file %s", stale)


_default_service: BackupService | None = None


def get_service() -> BackupService:
    global _default_service
    if _default_service is None:
        _default_service = BackupService()
    return _default_service
