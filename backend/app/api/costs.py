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


def _raise_if_from_after_to(from_: date, to: date) -> None:
    if from_ > to:
        raise HTTPException(
            status_code=422,
            detail="Ungültiger Zeitraum: 'from' muss kleiner oder gleich 'to' sein.",
        )


def _get_boundary_readings(
    db: Session, meter_id: int, from_: date, to: date
) -> tuple[models.Reading, models.Reading]:
    """Return the (start, end) readings for the range, or raise 404.

    Consumption is derived from two existing readings only (no
    interpolation or extrapolation in this iteration):
    start = reading with the smallest reading_date >= from,
    end   = reading with the largest reading_date <= to.
    """
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
    return start_reading, end_reading


def _raise_if_negative(consumption: Decimal) -> None:
    if consumption < 0:
        # E.g. a meter reset/rollover; not silently clamped or ignored.
        raise HTTPException(
            status_code=422,
            detail=(
                "Der ermittelte Verbrauch ist negativ "
                "(möglicher Zählerüberlauf). Bitte Zählerstände prüfen."
            ),
        )


def _get_covering_tariff(
    db: Session,
    meter_id: int,
    tariff_kind: models.TariffKind,
    from_: date,
    to: date,
) -> models.TariffPeriod:
    """Return the single tariff period fully covering [from, to], or 404.

    The range must be fully contained within one period; splitting
    proportionally across multiple periods (tariff change within the
    range) is out of scope.
    """
    tariff = (
        db.query(models.TariffPeriod)
        .filter(
            models.TariffPeriod.meter_id == meter_id,
            models.TariffPeriod.tariff_kind == tariff_kind,
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
    return tariff


def _get_meter_or_404(db: Session, meter_id: int) -> models.Meter:
    meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if meter is None:
        # Defensive: readings exist, so the meter must exist; kept for
        # type safety.
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden.")
    return meter


def _compute_cost_fields(
    consumption: Decimal, tariff: models.TariffPeriod, from_: date, to: date
) -> tuple[Decimal, Decimal]:
    """Compute (base_fee_total, total_cost) with the shared cost rules.

    Base fee proration uses a fixed 30-day month; money is rounded once
    at the output boundary (AGENTS.md).
    """
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
    return base_fee_total, total_cost


@router.get("/", response_model=schemas.CostCalculationResponse)
def calculate_costs(
    meter_id: int = Query(...),
    # "from" is a Python keyword, so the parameter is aliased in the
    # query string.
    from_: date = Query(..., alias="from"),  # noqa: B008 (FastAPI DI style)
    to: date = Query(...),  # noqa: B008 (FastAPI DI style)
    db: Session = Depends(get_database_session),  # noqa: B008 (existing pattern)
):
    _raise_if_from_after_to(from_, to)

    start_reading, end_reading = _get_boundary_readings(db, meter_id, from_, to)

    consumption = end_reading.value - start_reading.value
    _raise_if_negative(consumption)

    tariff = _get_covering_tariff(
        db, meter_id, models.TariffKind.CONSUMPTION, from_, to
    )
    meter = _get_meter_or_404(db, meter_id)

    base_fee_total, total_cost = _compute_cost_fields(consumption, tariff, from_, to)

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


@router.get("/wastewater/", response_model=schemas.WastewaterCostCalculationResponse)
def calculate_wastewater_costs(
    water_cold_meter_id: int = Query(...),
    # Optional: omitting the garden meter means "no garden meter
    # installed" - the entire cold-water consumption counts as wastewater.
    water_garden_meter_id: int | None = Query(None),
    # "from" is a Python keyword, so the parameter is aliased in the
    # query string.
    from_: date = Query(..., alias="from"),  # noqa: B008 (FastAPI DI style)
    to: date = Query(...),  # noqa: B008 (FastAPI DI style)
    db: Session = Depends(get_database_session),  # noqa: B008 (existing pattern)
):
    _raise_if_from_after_to(from_, to)

    start_reading, end_reading = _get_boundary_readings(
        db, water_cold_meter_id, from_, to
    )
    cold_consumption = end_reading.value - start_reading.value
    _raise_if_negative(cold_consumption)

    # If the garden meter parameter is provided but has no readings in
    # the range, this IS an error (same lookup logic as above): the
    # client explicitly claimed this meter is relevant. Only omitting
    # the parameter entirely triggers the "= 0" fallback.
    garden_consumption = Decimal(0)
    if water_garden_meter_id is not None:
        garden_start, garden_end = _get_boundary_readings(
            db, water_garden_meter_id, from_, to
        )
        garden_consumption = garden_end.value - garden_start.value
        # A garden consumption exceeding the cold consumption is a data
        # quality issue that is not validated here; the wastewater
        # consumption is simply floored at 0.
    wastewater_consumption = max(Decimal(0), cold_consumption - garden_consumption)

    # The wastewater tariff is attached to the cold-water meter.
    tariff = _get_covering_tariff(
        db, water_cold_meter_id, models.TariffKind.WASTEWATER, from_, to
    )
    meter = _get_meter_or_404(db, water_cold_meter_id)

    base_fee_total, total_cost = _compute_cost_fields(
        wastewater_consumption, tariff, from_, to
    )

    return schemas.WastewaterCostCalculationResponse(
        water_cold_meter_id=water_cold_meter_id,
        water_garden_meter_id=water_garden_meter_id,
        from_date=from_,
        to_date=to,
        cold_consumption=cold_consumption,
        garden_consumption=garden_consumption,
        wastewater_consumption=wastewater_consumption,
        unit=meter.unit,
        price_per_unit=tariff.price_per_unit,
        base_fee_total=base_fee_total,
        total_cost=total_cost,
    )
