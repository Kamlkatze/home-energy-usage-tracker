from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class CostCalculationResponse(BaseModel):
    meter_id: int
    from_date: date
    to_date: date
    consumption: Decimal
    unit: str
    price_per_unit: Decimal
    base_fee_total: Decimal
    total_cost: Decimal


class WastewaterCostCalculationResponse(BaseModel):
    water_cold_meter_id: int
    water_garden_meter_id: int | None
    from_date: date
    to_date: date
    cold_consumption: Decimal
    garden_consumption: Decimal
    wastewater_consumption: Decimal
    unit: str
    price_per_unit: Decimal
    base_fee_total: Decimal
    total_cost: Decimal


class AdvancePaymentDiffResponse(BaseModel):
    meter_id: int
    year: int
    estimated_or_actual_cost: str | None = None
    cost_basis: Literal["actual", "projected"] | None = None
    total_advance_payments: str | None = None
    difference: str | None = None
    message: str | None = None


class FeedInCompensationResponse(BaseModel):
    production_meter_id: int
    export_meter_id: int
    from_date: date
    to_date: date
    production_consumption: Decimal
    export_consumption: Decimal
    self_consumption: Decimal
    tier1_kwh: Decimal
    tier2_kwh: Decimal
    total_compensation: Decimal


class YearEntry(BaseModel):
    year: int
    consumption: str | None = None
    cost: str | None = None
    cost_basis: Literal["actual", "projected"] | None = None


class YearsOverviewItem(BaseModel):
    meter_id: int
    meter_label: str
    meter_type: str
    unit: str
    years: list[YearEntry]


class ConsumptionTimeseriesPoint(BaseModel):
    date: date
    value: str
    consumption_since_previous: str | None = None
    cost_since_previous: str | None = None


class ConsumptionTimeseriesItem(BaseModel):
    meter_id: int
    meter_label: str
    meter_type: str
    unit: str
    points: list[ConsumptionTimeseriesPoint]
