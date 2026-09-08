from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class ReadingBase(BaseModel):
    meter_id: int
    value: Decimal
    reading_date: date
    note: Optional[str] = None


class ReadingCreate(ReadingBase):
    pass


class ReadingUpdate(BaseModel):
    value: Optional[Decimal] = None
    reading_date: Optional[date] = None
    note: Optional[str] = None


class Reading(ReadingBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)