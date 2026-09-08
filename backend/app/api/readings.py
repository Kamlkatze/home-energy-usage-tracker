from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from .deps import get_database_session

router = APIRouter()


@router.get("/", response_model=List[schemas.Reading])
def read_readings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_database_session),
):
    readings = db.query(models.Reading).offset(skip).limit(limit).all()
    return readings


@router.get("/{reading_id}", response_model=schemas.Reading)
def read_reading(
    reading_id: int,
    db: Session = Depends(get_database_session),
):
    reading = db.query(models.Reading).filter(models.Reading.id == reading_id).first()
    if reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return reading


@router.post("/", response_model=schemas.Reading)
def create_reading(
    reading: schemas.ReadingCreate,
    db: Session = Depends(get_database_session),
):
    db_reading = models.Reading(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@router.put("/{reading_id}", response_model=schemas.Reading)
def update_reading(
    reading_id: int,
    reading_update: schemas.ReadingUpdate,
    db: Session = Depends(get_database_session),
):
    db_reading = db.query(models.Reading).filter(models.Reading.id == reading_id).first()
    if db_reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    
    update_data = reading_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_reading, field, value)
    
    db.commit()
    db.refresh(db_reading)
    return db_reading


@router.delete("/{reading_id}")
def delete_reading(
    reading_id: int,
    db: Session = Depends(get_database_session),
):
    db_reading = db.query(models.Reading).filter(models.Reading.id == reading_id).first()
    if db_reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    
    db.delete(db_reading)
    db.commit()
    return {"message": "Reading deleted successfully"}