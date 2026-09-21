import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class TariffKind(enum.Enum):
    CONSUMPTION = "consumption"
    FEED_IN = "feed_in"
    SELF_CONSUMPTION = "self_consumption"
    WASTEWATER = "wastewater"
    FEED_IN_EEG2009 = "feed_in_eeg2009"


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
    # Gas conversion factors (only meaningful for tariff_kind="consumption"
    # on meters with meter_type="gas"). Gas meters record consumption in m³,
    # but gas contracts bill in €/kWh:
    #   kWh = m³ * gas_z_zahl (Zustandszahl) * gas_brennwert (Brennwert, kWh/m³)
    # Both are optional/nullable. NOT enforced at the DB level (no CHECK
    # constraint) - enforced at the cost-calculation boundary instead, where
    # a missing value on a gas tariff raises a 422. They can change between
    # billing periods, so they are stored per TariffPeriod like the other
    # optional fee fields.
    gas_z_zahl: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    gas_brennwert: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    # EEG 2009 feed-in tariff fields (only meaningful for
    # tariff_kind="feed_in_eeg2009"). The tier rates reduce the compensation
    # for self-consumed electricity; metering_point_fee_yearly is a fixed
    # annual fee prorated by days (see feed-in-compensation endpoint).
    eeg_tier1_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    eeg_tier2_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 5))
    metering_point_fee_yearly: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    comment: Mapped[str | None] = mapped_column(String(500))

    meter: Mapped["Meter"] = relationship(back_populates="tariff_periods")