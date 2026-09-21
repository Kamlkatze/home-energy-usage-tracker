
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists as sa_exists
from sqlalchemy.orm import Session

from .. import models, schemas
from ..models.meter import METER_TYPE_LABELS, METER_TYPE_UNITS, MeterType
from .deps import get_database_session

router = APIRouter()


def _validate_replaces_meter(
    db: Session,
    replaces_meter_id: int,
    meter_type: MeterType,
    current_meter_id: int | None = None,
) -> None:
    """Validate that replaces_meter_id points to an existing meter of the same type.

    Raises 422 when:
    - replaces_meter_id references the meter itself (self-reference)
    - the referenced meter does not exist
    - the referenced meter has a different meter_type
    """
    if replaces_meter_id == current_meter_id:
        raise HTTPException(
            status_code=422,
            detail="Ein Zähler kann nicht sich selbst als Vorgänger referenzieren.",
        )
    predecessor = db.query(models.Meter).filter(models.Meter.id == replaces_meter_id).first()
    if predecessor is None:
        raise HTTPException(
            status_code=422,
            detail=f"Vorgänger-Zähler mit ID {replaces_meter_id} nicht gefunden.",
        )
    if predecessor.meter_type != meter_type:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Zählertyp-Konflikt: Vorgänger-Zähler hat Typ '{predecessor.meter_type.value}', "
                f"der neue Zähler hat Typ '{meter_type.value}'. "
                "Ein Zähler kann nur durch einen Zähler desselben Typs ersetzt werden."
            ),
        )


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


@router.get("/current", response_model=list[schemas.Meter])
def read_current_meters(
    db: Session = Depends(get_database_session),
):
    """Return only current (non-replaced) meters.

    A current meter is the newest meter in a replacement chain (or a standalone
    meter) — i.e. no other meter's replaces_meter_id points to it.
    """
    referenced_ids = (
        db.query(models.Meter.replaces_meter_id)
        .filter(models.Meter.replaces_meter_id.isnot(None))
        .distinct()
        .subquery()
    )
    meters = (
        db.query(models.Meter)
        .outerjoin(referenced_ids, models.Meter.id == referenced_ids.c.replaces_meter_id)
        .filter(referenced_ids.c.replaces_meter_id.is_(None))
        .order_by(models.Meter.id.asc())
        .all()
    )
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
    # The unit is always derived from meter_type and never taken from
    # client input (MeterCreate rejects a "unit" field with 422).
    if meter.replaces_meter_id is not None:
        _validate_replaces_meter(db, meter.replaces_meter_id, meter.meter_type)

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
        # Check if the meter_type is actually changing
        if update_data["meter_type"] != db_meter.meter_type:
            has_readings = db.query(
                sa_exists().where(models.Reading.meter_id == meter_id)
            ).scalar()
            if has_readings:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Der Zählertyp kann nicht geändert werden, da bereits "
                        "Zählerstände für diesen Zähler erfasst wurden."
                    ),
                )
        update_data["unit"] = METER_TYPE_UNITS[update_data["meter_type"]]

    # Determine effective meter_type and replaces_meter_id after update
    effective_meter_type: MeterType = update_data.get("meter_type", db_meter.meter_type)
    effective_replaces_id: int | None = update_data.get(
        "replaces_meter_id",
        db_meter.replaces_meter_id,
    )

    if effective_replaces_id is not None:
        _validate_replaces_meter(
            db, effective_replaces_id, effective_meter_type, current_meter_id=meter_id
        )

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
