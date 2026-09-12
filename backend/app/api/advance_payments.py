from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from .deps import get_database_session

router = APIRouter()


@router.get("/", response_model=list[schemas.AdvancePayment])
def read_advance_payments(
    skip: int = 0,
    limit: int = 100,
    meter_id: int | None = None,
    db: Session = Depends(get_database_session),
):
    query = db.query(models.AdvancePayment)
    if meter_id is not None:
        query = query.filter(models.AdvancePayment.meter_id == meter_id)
    payments = query.offset(skip).limit(limit).all()
    return payments


@router.get("/{payment_id}", response_model=schemas.AdvancePayment)
def read_advance_payment(
    payment_id: int,
    db: Session = Depends(get_database_session),
):
    payment = db.query(models.AdvancePayment).filter(models.AdvancePayment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Advance payment not found")
    return payment


@router.post("/", response_model=schemas.AdvancePayment)
def create_advance_payment(
    payment: schemas.AdvancePaymentCreate,
    db: Session = Depends(get_database_session),
):
    meter = db.query(models.Meter).filter(models.Meter.id == payment.meter_id).first()
    if meter is None:
        raise HTTPException(status_code=404, detail="Meter not found")

    db_payment = models.AdvancePayment(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


@router.put("/{payment_id}", response_model=schemas.AdvancePayment)
def update_advance_payment(
    payment_id: int,
    payment_update: schemas.AdvancePaymentUpdate,
    db: Session = Depends(get_database_session),
):
    db_payment = db.query(models.AdvancePayment).filter(models.AdvancePayment.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Advance payment not found")

    update_data = payment_update.model_dump(exclude_unset=True)

    if "meter_id" in update_data:
        meter = db.query(models.Meter).filter(models.Meter.id == update_data["meter_id"]).first()
        if meter is None:
            raise HTTPException(status_code=404, detail="Meter not found")

    for field, value in update_data.items():
        setattr(db_payment, field, value)

    db.commit()
    db.refresh(db_payment)
    return db_payment


@router.delete("/{payment_id}")
def delete_advance_payment(
    payment_id: int,
    db: Session = Depends(get_database_session),
):
    db_payment = db.query(models.AdvancePayment).filter(models.AdvancePayment.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Advance payment not found")

    db.delete(db_payment)
    db.commit()
    return {"message": "Advance payment deleted successfully"}