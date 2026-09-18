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
    # Gas conversion factors, only meaningful for tariff_kind="consumption"
    # on gas meters (meter_type="gas"). Optional; enforced at cost
    # calculation time for gas meters (missing values -> 422).
    gas_z_zahl: Decimal | None = None
    gas_brennwert: Decimal | None = None
    # EEG 2009 feed-in tariff fields (only meaningful for
    # tariff_kind="feed_in_eeg2009").
    eeg_tier1_rate: Decimal | None = None
    eeg_tier2_rate: Decimal | None = None
    metering_point_fee_yearly: Decimal | None = None
    comment: str | None = None


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
    gas_z_zahl: Decimal | None = None
    gas_brennwert: Decimal | None = None
    eeg_tier1_rate: Decimal | None = None
    eeg_tier2_rate: Decimal | None = None
    metering_point_fee_yearly: Decimal | None = None
    comment: str | None = None


class TariffPeriod(TariffPeriodBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TariffUsageResponse(BaseModel):
    tariff_id: int
    meter_id: int
    reading_count: int
    first_reading_date: date | None = None
    last_reading_date: date | None = None
    in_use: bool