from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from ..models.meter import MeterType


class MeterBase(BaseModel):
    meter_type: MeterType
    label: str
    unit: str


class MeterCreate(MeterBase):
    pass


class MeterUpdate(BaseModel):
    meter_type: Optional[MeterType] = None
    label: Optional[str] = None
    unit: Optional[str] = None


class Meter(MeterBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)