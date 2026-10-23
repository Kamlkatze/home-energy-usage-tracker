from pydantic import BaseModel


class BackupInfo(BaseModel):
    db_revision: str
    head_revision: str
    pg_version: str
    app_version: str


class RestoreResult(BaseModel):
    message: str
    dump_revision: str
    upgraded_to: str
