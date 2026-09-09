
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..models.meter import METER_TYPE_LABELS, METER_TYPE_UNITS, MeterType
from .deps import get_database_session

router = APIRouter()


@router.get("/", response_model=list[schemas.Meter])
def read_meters(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_database_session),
):
    meters = db.query(models.Meter).offset(skip).limit(limit).all()
    return meters


# NOTE: must be registered before GET /{meter_id}, otherwise "types" would
# be captured by the {meter_id} path parameter and fail int validation.
@router.get("/types", response_model=list[schemas.MeterTypeInfo])
def read_meter_types():
    """List all meter types with their German label and fixed unit."""
    return [
        schemas.MeterTypeInfo(
            value=meter_type,
            label=METER_TYPE_LABELS[meter_type],
            unit=METER_TYPE_UNITS[meter_type],
        )
        for meter_type in MeterType
    ]


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
    # The unit is always derived from meter_type and never taken from
    # client input (MeterCreate rejects a "unit" field with 422).
    db_meter = models.Meter(
        **meter.model_dump(),
        unit=METER_TYPE_UNITS[meter.meter_type],
    )
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
    # The unit is derived from meter_type (never client-settable), so it must
    # be re-derived whenever the meter type changes in an update.
    if "meter_type" in update_data:
        update_data["unit"] = METER_TYPE_UNITS[update_data["meter_type"]]
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


@router.get("/{meter_id}/readings", response_model=list[schemas.Reading])
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