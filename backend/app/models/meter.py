import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .reading import Reading
    from .tariff_period import TariffPeriod


class MeterType(str, enum.Enum):
    GAS = "gas"
    WATER_COLD = "water_cold"
    WATER_GARDEN = "water_garden"
    ELECTRICITY_IMPORT = "electricity_import"
    ELECTRICITY_EXPORT = "electricity_export"
    ELECTRICITY_PRODUCTION = "electricity_production"


# Maps each meter type to its fixed unit of measurement.
# Units are not user-configurable — they are implied by the meter type.
METER_TYPE_UNITS: dict[MeterType, str] = {
    MeterType.GAS: "m³",
    MeterType.WATER_COLD: "m³",
    MeterType.WATER_GARDEN: "m³",
    MeterType.ELECTRICITY_IMPORT: "kWh",
    MeterType.ELECTRICITY_EXPORT: "kWh",
    MeterType.ELECTRICITY_PRODUCTION: "kWh",
}

# German display labels for each meter type, used by the
# GET /api/meters/types endpoint consumed by the frontend.
METER_TYPE_LABELS: dict[MeterType, str] = {
    MeterType.GAS: "Gas",
    MeterType.WATER_COLD: "Kaltwasser",
    MeterType.WATER_GARDEN: "Gartenwasser",
    MeterType.ELECTRICITY_IMPORT: "Strom Bezug",
    MeterType.ELECTRICITY_EXPORT: "Strom Einspeisung",
    MeterType.ELECTRICITY_PRODUCTION: "Strom Erzeugung",
}


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