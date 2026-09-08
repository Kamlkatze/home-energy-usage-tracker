from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .meter import Meter


class Reading(Base, TimestampMixin):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("meter_id", "reading_date", name="uq_meter_reading_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    reading_date: Mapped[Date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    
    meter: Mapped["Meter"] = relationship(back_populates="readings")