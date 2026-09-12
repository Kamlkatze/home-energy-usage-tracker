from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class YearlyProjectionWithCostResponse(BaseModel):
    """Response schema for yearly projection with cost calculation."""
    
    meter_id: int
    year: int
    unit: str
    as_of_date: date
    actual_consumption_to_date: Decimal | None
    projected_annual_consumption: Decimal | None
    basis: Literal[
        "linear_from_prev_year_end",
        "linear_from_first_reading_of_year",
        "actual_full_year",
        "insufficient_data",
    ]
    actual_cost_to_date: Decimal | None
    projected_annual_cost: Decimal | None
    message: str | None = None