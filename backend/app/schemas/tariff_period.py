from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class TariffPeriodBase(BaseModel):
    meter_id: int
    valid_from: date
    valid_to: Optional[date] = None
    price_per_unit: Decimal
    base_fee_monthly: Optional[Decimal] = None


class TariffPeriodCreate(TariffPeriodBase):
    pass


class TariffPeriodUpdate(BaseModel):
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    price_per_unit: Optional[Decimal] = None
    base_fee_monthly: Optional[Decimal] = None


class TariffPeriod(TariffPeriodBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)