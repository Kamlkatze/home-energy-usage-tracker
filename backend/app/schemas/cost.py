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
