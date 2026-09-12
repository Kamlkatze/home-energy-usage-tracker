import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class TariffKind(enum.Enum):
    CONSUMPTION = "consumption"
    FEED_IN = "feed_in"
    SELF_CONSUMPTION = "self_consumption"
    WASTEWATER = "wastewater"


class TariffPeriod(Base, TimestampMixin):
    __tablename__ = "tariff_periods"

    # valid_to semantics:
    # - nullable: NULL means open-ended, i.e. the period is still valid today
    #   until it is given an end date (or is superseded).
    # - inclusive: both valid_from and valid_to are part of the period
    #   (the DB EXCLUDE constraint uses daterange(valid_from, valid_to, '[]')).
    #   Adjacent periods must therefore use valid_to = day before the next
    #   valid_from (e.g. ..2024-12-31 and 2025-01-01..).
    #
    # Overlap rule (enforced by excl_tariff_period_no_overlap in the DB,
    # defined in the migration): periods of the same (meter_id, tariff_kind)
    # must not overlap; different tariff_kind values may overlap in time.
    # Note: the EXCLUDE constraint fully covers the former
    # UNIQUE(meter_id, valid_from) constraint (same start date always
    # overlaps, because the lower range bound is inclusive).

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"))
    tariff_kind: Mapped[TariffKind] = mapped_column(
        Enum(TariffKind, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    base_fee_monthly: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    metering_fee_monthly: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    
    meter: Mapped["Meter"] = relationship(back_populates="tariff_periods")