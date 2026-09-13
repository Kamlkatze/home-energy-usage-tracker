
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..services.meter_chain import get_full_meter_chain_ids
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


@router.get("/{tariff_id}/usage", response_model=schemas.TariffUsageResponse)
def read_tariff_usage(
    tariff_id: int,
    db: Session = Depends(get_database_session),
):
    tariff = db.query(models.TariffPeriod).filter(models.TariffPeriod.id == tariff_id).first()
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff period not found")

    chain_ids = get_full_meter_chain_ids(db, tariff.meter_id)

    today = datetime.now(UTC).date()
    range_end = tariff.valid_to if tariff.valid_to is not None else today

    count_value, min_date, max_date = (
        db.query(
            func.count(models.Reading.id),
            func.min(models.Reading.reading_date),
            func.max(models.Reading.reading_date),
        )
        .filter(
            models.Reading.meter_id.in_(chain_ids),
            models.Reading.reading_date >= tariff.valid_from,
            models.Reading.reading_date <= range_end,
        )
        .first()
        or (0, None, None)
    )

    reading_count = count_value or 0
    first_reading_date = min_date
    last_reading_date = max_date

    return schemas.TariffUsageResponse(
        tariff_id=tariff.id,
        meter_id=tariff.meter_id,
        reading_count=reading_count,
        first_reading_date=first_reading_date,
        last_reading_date=last_reading_date,
        in_use=reading_count > 0,
    )