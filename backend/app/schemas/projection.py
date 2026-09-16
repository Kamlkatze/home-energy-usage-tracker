from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ProjectionResponse(BaseModel):
    meter_id: int
    year: int
    unit: str
    actual_consumption_to_date: Decimal | None
    days_elapsed: int | None
    projected_annual_consumption: Decimal | None
    projected_meter_reading_end_of_year: Decimal | None
    basis: Literal[
        "linear_from_prev_year_end",
        "linear_from_first_reading_of_year",
        "actual_full_year",
        "insufficient_data",
    ]
    message: str | None = None