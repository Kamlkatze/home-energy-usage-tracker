import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .reading import Reading
    from .tariff_period import TariffPeriod


class MeterType(enum.Enum):
    ELECTRICITY = "electricity"
    GAS = "gas"
    WATER = "water"


class Meter(Base, TimestampMixin):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_type: Mapped[MeterType] = mapped_column(
        Enum(MeterType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    
    readings: Mapped[list["Reading"]] = relationship(
        back_populates="meter", cascade="all, delete-orphan"
    )
    tariff_periods: Mapped[list["TariffPeriod"]] = relationship(
        back_populates="meter", cascade="all, delete-orphan"
    )