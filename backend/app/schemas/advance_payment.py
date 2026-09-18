from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from ..models.advance_payment import AdvancePaymentCategory


class AdvancePaymentBase(BaseModel):
    category: AdvancePaymentCategory
    meter_id: int | None = None
    water_cold_meter_id: int | None = None
    water_garden_meter_id: int | None = None
    valid_from: date
    valid_to: date | None = None
    monthly_amount: Decimal
    comment: str | None = None


class AdvancePaymentCreate(AdvancePaymentBase):
    @model_validator(mode="after")
    def validate_category_fields(self):
        if self.category == AdvancePaymentCategory.WASTEWATER:
            if self.meter_id is not None:
                raise ValueError(
                    "meter_id must be null for wastewater category"
                )
            if self.water_cold_meter_id is None:
                raise ValueError(
                    "water_cold_meter_id is required for wastewater category"
                )
        else:
            if self.meter_id is None:
                raise ValueError(
                    "meter_id is required for non-wastewater categories"
                )
            if self.water_cold_meter_id is not None:
                raise ValueError(
                    "water_cold_meter_id must be null for non-wastewater categories"
                )
            if self.water_garden_meter_id is not None:
                raise ValueError(
                    "water_garden_meter_id must be null for non-wastewater categories"
                )
        return self


class AdvancePaymentUpdate(BaseModel):
    category: AdvancePaymentCategory | None = None
    meter_id: int | None = None
    water_cold_meter_id: int | None = None
    water_garden_meter_id: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    monthly_amount: Decimal | None = None
    comment: str | None = None

    @model_validator(mode="after")
    def validate_category_fields(self):
        if self.category is not None:
            if self.category == AdvancePaymentCategory.WASTEWATER:
                if self.meter_id is not None:
                    raise ValueError(
                        "meter_id must be null for wastewater category"
                    )
                if (
                    "water_cold_meter_id" in self.model_fields_set
                    and self.water_cold_meter_id is None
                ):
                    raise ValueError(
                        "water_cold_meter_id is required for wastewater category"
                    )
            else:
                if (
                    "meter_id" in self.model_fields_set
                    and self.meter_id is None
                ):
                    raise ValueError(
                        "meter_id is required for non-wastewater categories"
                    )
                if self.water_cold_meter_id is not None:
                    raise ValueError(
                        "water_cold_meter_id must be null for non-wastewater categories"
                    )
                if self.water_garden_meter_id is not None:
                    raise ValueError(
                        "water_garden_meter_id must be null for non-wastewater categories"
                    )
        return self


class AdvancePayment(AdvancePaymentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)