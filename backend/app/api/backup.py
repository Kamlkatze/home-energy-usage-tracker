import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from ..config import settings
from ..schemas.backup import BackupInfo, RestoreResult
from ..services.backup import (
    BackupConflictError,
    BackupError,
    BackupExecutionError,
    BackupService,
    get_service,
)

router = APIRouter()

_READ_CHUNK = 1024 * 1024


@router.get("/info", response_model=BackupInfo)
async def get_backup_info(
    service: BackupService = Depends(get_service),
) -> BackupInfo:
    try:
        info = await service.get_info()
    except BackupExecutionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return BackupInfo(**info)


@router.get("/dump")
async def download_backup(
    service: BackupService = Depends(get_service),
) -> StreamingResponse:
    if service.lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Es läuft bereits ein Backup- oder Restore-Vorgang. Bitte kurz warten.",
        )
    try:
        filename, stream = await service.create_dump_stream()
    except BackupExecutionError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore", response_model=RestoreResult)
async def restore_backup(
    file: UploadFile = File(...),
    confirm: str = Form(...),
    service: BackupService = Depends(get_service),
) -> RestoreResult:
    if confirm.lower() != "true":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Die Wiederherstellung muss ausdrücklich bestätigt werden.",
        )
    if not (file.filename or "").lower().endswith(".sql"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bitte eine .sql-Backup-Datei auswählen.",
        )
    if service.lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Es läuft bereits ein Backup- oder Restore-Vorgang. Bitte kurz warten.",
        )

    fd, tmp_name = tempfile.mkstemp(prefix="restore-", suffix=".sql")
    try:
        total = 0
        with os.fdopen(fd, "wb") as fh:
            while chunk := await file.read(_READ_CHUNK):
                total += len(chunk)
                if total > settings.BACKUP_MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "Die Datei ist zu groß (Maximum "
                        f"{settings.BACKUP_MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
                    )
                fh.write(chunk)
        path = Path(tmp_name)
        try:
            validation = await service.validate_dump_file(path)
            result = await service.restore(path, validation)
        except BackupConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        except BackupExecutionError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
        except BackupError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        return RestoreResult(**result)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
