from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from .deps import get_database_session

router = APIRouter()

# Money is rounded once, at the response boundary (never on intermediate
# values, per AGENTS.md).
_CENT = Decimal("0.01")

# Base fee proration uses a fixed 30-day month (intentional simplification;
# calendar-accurate month lengths are out of scope for this iteration).
_DAYS_PER_MONTH = Decimal(30)


@router.get("/", response_model=schemas.CostCalculationResponse)
def calculate_costs(
    meter_id: int = Query(...),
    # "from" is a Python keyword, so the parameter is aliased in the
    # query string.
    from_: date = Query(..., alias="from"),  # noqa: B008 (FastAPI DI style)
    to: date = Query(...),  # noqa: B008 (FastAPI DI style)
    db: Session = Depends(get_database_session),  # noqa: B008 (existing pattern)
):
    if from_ > to:
        raise HTTPException(
            status_code=422,
            detail="Ungültiger Zeitraum: 'from' muss kleiner oder gleich 'to' sein.",
        )

    # Consumption is derived from two existing readings only (no
    # interpolation or extrapolation in this iteration):
    # start = reading with the smallest reading_date >= from,
    # end   = reading with the largest reading_date <= to.
    start_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date >= from_,
        )
        .order_by(models.Reading.reading_date.asc())
        .first()
    )
    end_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date <= to,
        )
        .order_by(models.Reading.reading_date.desc())
        .first()
    )
    if start_reading is None or end_reading is None:
        raise HTTPException(
            status_code=404,
            detail="Kein Zählerstand im angegebenen Zeitraum gefunden.",
        )

    consumption = end_reading.value - start_reading.value
    if consumption < 0:
        # E.g. a meter reset/rollover; not silently clamped or ignored.
        raise HTTPException(
            status_code=422,
            detail=(
                "Der ermittelte Verbrauch ist negativ "
                "(möglicher Zählerüberlauf). Bitte Zählerstände prüfen."
            ),
        )

    # The range [from, to] must be fully contained within a single
    # consumption tariff period; splitting proportionally across multiple
    # periods (tariff change within the range) is out of scope.
    tariff = (
        db.query(models.TariffPeriod)
        .filter(
            models.TariffPeriod.meter_id == meter_id,
            models.TariffPeriod.tariff_kind == models.TariffKind.CONSUMPTION,
            models.TariffPeriod.valid_from <= from_,
            or_(
                models.TariffPeriod.valid_to.is_(None),
                models.TariffPeriod.valid_to >= to,
            ),
        )
        .first()
    )
    if tariff is None:
        raise HTTPException(
            status_code=404,
            detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
        )

    meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if meter is None:
        # Defensive: readings exist, so the meter must exist; kept for
        # type safety.
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden.")

    # days_in_range is inclusive-exclusive: 'from' counts, 'to' does not
    # (e.g. from=2024-01-10, to=2024-01-11 => 1 day).
    days_in_range = Decimal((to - from_).days)

    # A null base_fee_monthly is treated as 0.
    base_fee_monthly = (
        tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
    )
    base_fee_total_raw = base_fee_monthly * days_in_range / _DAYS_PER_MONTH

    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total_cost = (consumption * tariff.price_per_unit + base_fee_total_raw).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )

    return schemas.CostCalculationResponse(
        meter_id=meter_id,
        from_date=from_,
        to_date=to,
        consumption=consumption,
        unit=meter.unit,
        price_per_unit=tariff.price_per_unit,
        base_fee_total=base_fee_total,
        total_cost=total_cost,
    )
