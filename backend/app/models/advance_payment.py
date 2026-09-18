from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class AdvancePaymentCategory(str, enum.Enum):
    GAS = "gas"
    COLD_WATER = "cold_water"
    WASTEWATER = "wastewater"
    POWER_IMPORT = "power_import"


class AdvancePayment(Base, TimestampMixin):
    __tablename__ = "advance_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category: Mapped[AdvancePaymentCategory] = mapped_column(
        Enum(
            AdvancePaymentCategory,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    meter_id: Mapped[int | None] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"), nullable=True
    )
    water_cold_meter_id: Mapped[int | None] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"), nullable=True
    )
    water_garden_meter_id: Mapped[int | None] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"), nullable=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    meter: Mapped[Meter | None] = relationship(
        back_populates="advance_payments",
        foreign_keys=[meter_id],
    )
    water_cold_meter: Mapped[Meter | None] = relationship(
        foreign_keys=[water_cold_meter_id],
    )
    water_garden_meter: Mapped[Meter | None] = relationship(
        foreign_keys=[water_garden_meter_id],
    )

    __table_args__ = (
        CheckConstraint(
            "NOT (category = 'wastewater') "
            "OR (meter_id IS NULL AND water_cold_meter_id IS NOT NULL)",
            name="ck_advance_payment_wastewater",
        ),
        CheckConstraint(
            "(category = 'wastewater') "
            "OR (meter_id IS NOT NULL AND water_cold_meter_id IS NULL "
            "AND water_garden_meter_id IS NULL)",
            name="ck_advance_payment_non_wastewater",
        ),
    )