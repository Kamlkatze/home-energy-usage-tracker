from datetime import date
from decimal import Decimal

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
