from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
from ..database import get_db


def get_database_session(
    db: Session = Depends(get_db)
) -> Generator[Session, None, None]:
    yield db