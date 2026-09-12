from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ..models import TariffKind


class TariffPeriodBase(BaseModel):
    meter_id: int
    tariff_kind: TariffKind
    valid_from: date
    valid_to: date | None = None
    price_per_unit: Decimal
    base_fee_monthly: Decimal | None = None
    metering_fee_monthly: Decimal | None = None


class TariffPeriodCreate(TariffPeriodBase):
    # Existing clients may omit tariff_kind; plain consumption price is the default
    tariff_kind: TariffKind = TariffKind.CONSUMPTION


class TariffPeriodUpdate(BaseModel):
    tariff_kind: TariffKind | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    price_per_unit: Decimal | None = None
    base_fee_monthly: Decimal | None = None
    metering_fee_monthly: Decimal | None = None


class TariffPeriod(TariffPeriodBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)