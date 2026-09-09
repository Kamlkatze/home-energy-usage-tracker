
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from .deps import get_database_session

router = APIRouter()


@router.get("/", response_model=list[schemas.TariffPeriod])
def read_tariff_periods(
    skip: int = 0,
    limit: int = 100,
    tariff_kind: models.TariffKind | None = None,
    db: Session = Depends(get_database_session),
):
    query = db.query(models.TariffPeriod)
    if tariff_kind is not None:
        query = query.filter(models.TariffPeriod.tariff_kind == tariff_kind)
    periods = query.offset(skip).limit(limit).all()
    return periods


@router.get("/{period_id}", response_model=schemas.TariffPeriod)
def read_tariff_period(
    period_id: int,
    db: Session = Depends(get_database_session),
):
    period = db.query(models.TariffPeriod).filter(models.TariffPeriod.id == period_id).first()
    if period is None:
        raise HTTPException(status_code=404, detail="Tariff period not found")
    return period


@router.post("/", response_model=schemas.TariffPeriod)
def create_tariff_period(
    period: schemas.TariffPeriodCreate,
    db: Session = Depends(get_database_session),
):
    # Check if meter exists
    meter = db.query(models.Meter).filter(models.Meter.id == period.meter_id).first()
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    db_period = models.TariffPeriod(**period.model_dump())
    db.add(db_period)
    db.commit()
    db.refresh(db_period)
    return db_period


@router.put("/{period_id}", response_model=schemas.TariffPeriod)
def update_tariff_period(
    period_id: int,
    period_update: schemas.TariffPeriodUpdate,
    db: Session = Depends(get_database_session),
):
    db_period = db.query(models.TariffPeriod).filter(models.TariffPeriod.id == period_id).first()
    if db_period is None:
        raise HTTPException(status_code=404, detail="Tariff period not found")
    
    update_data = period_update.model_dump(exclude_unset=True)
    
    # Check if meter_id is being updated and if the new meter exists
    if "meter_id" in update_data:
        meter = db.query(models.Meter).filter(models.Meter.id == update_data["meter_id"]).first()
        if meter is None:
            raise HTTPException(status_code=404, detail="Meter not found")
    
    for field, value in update_data.items():
        setattr(db_period, field, value)
    
    db.commit()
    db.refresh(db_period)
    return db_period


@router.delete("/{period_id}")
def delete_tariff_period(
    period_id: int,
    db: Session = Depends(get_database_session),
):
    db_period = db.query(models.TariffPeriod).filter(models.TariffPeriod.id == period_id).first()
    if db_period is None:
        raise HTTPException(status_code=404, detail="Tariff period not found")
    
    db.delete(db_period)
    db.commit()
    return {"message": "Tariff period deleted successfully"}