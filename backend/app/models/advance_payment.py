from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class AdvancePayment(Base, TimestampMixin):
    __tablename__ = "advance_payments"

    # An advance payment (Abschlag) is the monthly amount the customer pays
    # to the energy provider, independent of the actual tariff. Payments are
    # valid for a time range that is adjusted periodically.
    #
    # valid_to semantics (same as TariffPeriod):
    # - nullable: NULL means open-ended, i.e. the payment is still in effect.
    # - inclusive: both valid_from and valid_to are part of the period
    #   (the DB EXCLUDE constraint uses daterange(valid_from, valid_to, '[]')).
    #   Adjacent periods must therefore use valid_to = day before the next
    #   valid_from (e.g. ..2024-12-31 and 2025-01-01..).
    #
    # Overlap rule (enforced by excl_advance_payment_no_overlap in the DB,
    # defined in the migration): periods of the same meter_id must not overlap.
    #
    # Referential integrity: meter_id has a hard FK to meters.id (CASCADE).
    # The requirement that the meter has a TariffPeriod of
    # tariff_kind='consumption' is NOT enforced as a DB constraint; it is
    # checked in the API layer instead (see app/api/advance_payments.py).

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    meter: Mapped["Meter"] = relationship(back_populates="advance_payments")
