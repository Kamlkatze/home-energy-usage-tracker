from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AdvancePaymentBase(BaseModel):
    meter_id: int
    valid_from: date
    valid_to: date | None = None
    monthly_amount: Decimal


class AdvancePaymentCreate(AdvancePaymentBase):
    pass


class AdvancePaymentUpdate(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None
    monthly_amount: Decimal | None = None


class AdvancePayment(AdvancePaymentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)