from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ReadingBase(BaseModel):
    meter_id: int
    value: Decimal
    reading_date: date
    note: str | None = None


class ReadingCreate(ReadingBase):
    pass


class ReadingUpdate(BaseModel):
    value: Decimal | None = None
    reading_date: date | None = None
    note: str | None = None


class Reading(ReadingBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)