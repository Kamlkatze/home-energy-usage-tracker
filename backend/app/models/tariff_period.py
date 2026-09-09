from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class TariffPeriod(Base, TimestampMixin):
    __tablename__ = "tariff_periods"
    __table_args__ = (
        UniqueConstraint("meter_id", "valid_from", name="uq_meter_valid_from"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"))
    valid_from: Mapped[Date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Date | None] = mapped_column(Date)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 5), nullable=False)
    base_fee_monthly: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    
    meter: Mapped["Meter"] = relationship(back_populates="tariff_periods")