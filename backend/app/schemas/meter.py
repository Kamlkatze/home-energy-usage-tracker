from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..models.meter import MeterType


class MeterBase(BaseModel):
    meter_type: MeterType
    label: str
    meter_number: str | None = None
    # Optional: ID of the meter this one physically replaced.
    replaces_meter_id: int | None = None


class MeterCreate(MeterBase):
    # extra="forbid": clients must not send fields outside this schema.
    # In particular a "unit" field is rejected with 422 - the unit is
    # derived server-side from meter_type and is never client-settable.
    model_config = ConfigDict(extra="forbid")


class MeterUpdate(BaseModel):
    # extra="forbid": same rationale as MeterCreate - a client-supplied
    # "unit" field is rejected with 422 instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")

    meter_type: MeterType | None = None
    label: str | None = None
    meter_number: str | None = None
    replaces_meter_id: int | None = None


class Meter(MeterBase):
    # unit is read-only here: it only appears in responses and is always
    # derived server-side from meter_type (see models.meter.METER_TYPE_UNITS).
    unit: str

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeterTypeInfo(BaseModel):
    """One entry of the GET /api/meters/types response."""

    value: MeterType
    label: str
    unit: str
