from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from .deps import get_database_session

router = APIRouter()


@router.get("/", response_model=List[schemas.Meter])
def read_meters(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_database_session),
):
    meters = db.query(models.Meter).offset(skip).limit(limit).all()
    return meters


@router.get("/{meter_id}", response_model=schemas.Meter)
def read_meter(
    meter_id: int,
    db: Session = Depends(get_database_session),
):
    meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    return meter


@router.post("/", response_model=schemas.Meter)
def create_meter(
    meter: schemas.MeterCreate,
    db: Session = Depends(get_database_session),
):
    db_meter = models.Meter(**meter.model_dump())
    db.add(db_meter)
    db.commit()
    db.refresh(db_meter)
    return db_meter


@router.put("/{meter_id}", response_model=schemas.Meter)
def update_meter(
    meter_id: int,
    meter_update: schemas.MeterUpdate,
    db: Session = Depends(get_database_session),
):
    db_meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if db_meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    update_data = meter_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_meter, field, value)
    
    db.commit()
    db.refresh(db_meter)
    return db_meter


@router.delete("/{meter_id}")
def delete_meter(
    meter_id: int,
    db: Session = Depends(get_database_session),
):
    db_meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if db_meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    db.delete(db_meter)
    db.commit()
    return {"message": "Meter deleted successfully"}


@router.get("/{meter_id}/readings", response_model=List[schemas.Reading])
def read_meter_readings(
    meter_id: int,
    db: Session = Depends(get_database_session),
):
    meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    readings = (
        db.query(models.Reading)
        .filter(models.Reading.meter_id == meter_id)
        .order_by(models.Reading.reading_date)
        .all()
    )
    return readings