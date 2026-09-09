from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..models.meter import MeterType


class MeterBase(BaseModel):
    meter_type: MeterType
    label: str
    unit: str


class MeterCreate(MeterBase):
    pass


class MeterUpdate(BaseModel):
    meter_type: MeterType | None = None
    label: str | None = None
    unit: str | None = None


class Meter(MeterBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)