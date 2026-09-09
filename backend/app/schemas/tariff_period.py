from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TariffPeriodBase(BaseModel):
    meter_id: int
    valid_from: date
    valid_to: date | None = None
    price_per_unit: Decimal
    base_fee_monthly: Decimal | None = None


class TariffPeriodCreate(TariffPeriodBase):
    pass


class TariffPeriodUpdate(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None
    price_per_unit: Decimal | None = None
    base_fee_monthly: Decimal | None = None


class TariffPeriod(TariffPeriodBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)