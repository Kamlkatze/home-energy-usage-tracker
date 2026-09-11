from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..services.projection import ProjectionService
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


def _get_overlapping_tariffs(
    db: Session,
    meter_id: int,
    tariff_kind: models.TariffKind,
    from_: date,
    to: date,
) -> list[models.TariffPeriod]:
    """Return all tariff periods overlapping with [from, to], sorted by valid_from.

    The range must be fully covered by one or more consecutive periods.
    Consumption is allocated proportionally by days in each overlapping period.
    """
    tariffs = (
        db.query(models.TariffPeriod)
        .filter(
            models.TariffPeriod.meter_id == meter_id,
            models.TariffPeriod.tariff_kind == tariff_kind,
            models.TariffPeriod.valid_from <= to,
            or_(
                models.TariffPeriod.valid_to.is_(None),
                models.TariffPeriod.valid_to >= from_,
            ),
        )
        .order_by(models.TariffPeriod.valid_from.asc())
        .all()
    )
    
    if not tariffs:
        raise HTTPException(
            status_code=404,
            detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
        )
    
    # Verify the range is fully covered by consecutive periods
    # First, check if the first period covers the start
    if tariffs[0].valid_from > from_:
        raise HTTPException(
            status_code=404,
            detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
        )
    
    # Check for gaps between periods
    for i in range(len(tariffs) - 1):
        current = tariffs[i]
        next_period = tariffs[i + 1]
        
        # If current period has an end date, check that next period starts immediately after
        if current.valid_to is not None:
            # Add one day because valid_to is inclusive
            next_day = current.valid_to + timedelta(days=1)
            if next_period.valid_from > next_day:
                # Gap detected
                raise HTTPException(
                    status_code=404,
                    detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
                )
    
    # Check if the range extends beyond the last period
    last_tariff = tariffs[-1]
    if last_tariff.valid_to is not None and last_tariff.valid_to < to:
        raise HTTPException(
            status_code=404,
            detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
        )
    
    return tariffs


def _get_boundary_readings_for_yearly_cost(
    db: Session, meter_id: int, year: int, as_of_date: date
) -> tuple[models.Reading, models.Reading] | tuple[None, None]:
    """Find boundary readings for yearly cost calculation.
    
    Similar to projection logic:
    - Start: prefer reading on Dec 31 of previous year, fallback to first reading in year
    - End: last reading <= as_of_date
    """
    # Try to get reading from previous year's end exactly
    prev_year_end = date(year - 1, 12, 31)
    prev_year_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date == prev_year_end
        )
        .first()
    )
    
    if prev_year_reading:
        start_reading = prev_year_reading
    else:
        # Fallback to first reading in the target year
        year_start = date(year, 1, 1)
        start_reading = (
            db.query(models.Reading)
            .filter(
                models.Reading.meter_id == meter_id,
                models.Reading.reading_date >= year_start,
                models.Reading.reading_date <= as_of_date
            )
            .order_by(models.Reading.reading_date.asc())
            .first()
        )
    
    # End reading: last reading <= as_of_date
    end_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date <= as_of_date
        )
        .order_by(models.Reading.reading_date.desc())
        .first()
    )
    
    if not start_reading or not end_reading:
        return None, None
    
    # Check if start and end are valid (end > start)
    if end_reading.reading_date <= start_reading.reading_date:
        return None, None
    
    return start_reading, end_reading


def _get_active_tariff_for_date(
    db: Session,
    meter_id: int,
    tariff_kind: models.TariffKind,
    target_date: date,
) -> models.TariffPeriod | None:
    """Get the tariff period active on a specific date.
    
    Returns the tariff period where target_date falls within [valid_from, valid_to]
    (both bounds inclusive) or valid_to is NULL (open-ended).
    Returns None if no active tariff found.
    """
    return (
        db.query(models.TariffPeriod)
        .filter(
            models.TariffPeriod.meter_id == meter_id,
            models.TariffPeriod.tariff_kind == tariff_kind,
            models.TariffPeriod.valid_from <= target_date,
            or_(
                models.TariffPeriod.valid_to.is_(None),
                models.TariffPeriod.valid_to >= target_date,
            ),
        )
        .first()
    )


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
    """Compute (base_fee_total, total_cost) for a single tariff period.

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


def _compute_cost_fields_multiperiod(
    consumption: Decimal, tariffs: list[models.TariffPeriod], from_: date, to: date
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (base_fee_total, total_cost, first_price_per_unit) for multiple periods.

    Consumption is allocated proportionally by overlapping days in each period.
    Base fee proration uses a fixed 30-day month; money is rounded once
    at the output boundary (AGENTS.md).
    
    Date range semantics:
    - The requested range [from_, to) is inclusive-exclusive: 'from_' counts, 'to' does not.
    - Tariff periods [valid_from, valid_to] are inclusive on both ends (DB daterange '[]').
    - Overlap calculation converts tariff periods to exclusive end: [valid_from, valid_to + 1 day).
    - Consumption is allocated proportionally by days in each overlapping subrange.
    
    Returns the first period's price_per_unit for backward compatibility in API response.
    """
    total_days = Decimal((to - from_).days)
    if total_days == 0:
        # Should not happen due to _raise_if_from_after_to, but handle defensively
        total_days = Decimal("0.000001")
    
    base_fee_total_raw = Decimal(0)
    energy_cost_raw = Decimal(0)
    
    for tariff in tariffs:
        # Calculate overlap between [from_, to] and [tariff.valid_from, tariff.valid_to]
        period_start = max(from_, tariff.valid_from)
        period_end = to
        if tariff.valid_to is not None:
            period_end = min(to, tariff.valid_to + timedelta(days=1))  # valid_to is inclusive
        
        overlap_days = Decimal((period_end - period_start).days)
        if overlap_days <= 0:
            continue
            
        # Allocate consumption proportionally
        consumption_in_period = consumption * overlap_days / total_days
        
        # A null base_fee_monthly is treated as 0.
        base_fee_monthly = (
            tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
        )
        base_fee_total_raw += base_fee_monthly * overlap_days / _DAYS_PER_MONTH
        energy_cost_raw += consumption_in_period * tariff.price_per_unit
    
    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total_cost = (energy_cost_raw + base_fee_total_raw).quantize(_CENT, rounding=ROUND_HALF_UP)
    
    # Return first period's price for backward compatibility
    first_price_per_unit = tariffs[0].price_per_unit
    
    return base_fee_total, total_cost, first_price_per_unit


@router.get("/", response_model=schemas.CostCalculationResponse)
def calculate_costs(
    meter_id: int = Query(...),
    # "from" is a Python keyword, so the parameter is aliased in the
    # query string.
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_database_session),
):
    _raise_if_from_after_to(from_, to)

    start_reading, end_reading = _get_boundary_readings(db, meter_id, from_, to)

    consumption = end_reading.value - start_reading.value
    _raise_if_negative(consumption)

    tariffs = _get_overlapping_tariffs(
        db, meter_id, models.TariffKind.CONSUMPTION, from_, to
    )
    meter = _get_meter_or_404(db, meter_id)

    base_fee_total, total_cost, price_per_unit = _compute_cost_fields_multiperiod(
        consumption, tariffs, from_, to
    )

    return schemas.CostCalculationResponse(
        meter_id=meter_id,
        from_date=from_,
        to_date=to,
        consumption=consumption,
        unit=meter.unit,
        price_per_unit=price_per_unit,
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
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_database_session),
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
    tariffs = _get_overlapping_tariffs(
        db, water_cold_meter_id, models.TariffKind.WASTEWATER, from_, to
    )
    meter = _get_meter_or_404(db, water_cold_meter_id)

    base_fee_total, total_cost, price_per_unit = _compute_cost_fields_multiperiod(
        wastewater_consumption, tariffs, from_, to
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
        price_per_unit=price_per_unit,
        base_fee_total=base_fee_total,
        total_cost=total_cost,
    )

@router.get("/yearly-projection", response_model=schemas.YearlyProjectionWithCostResponse)
def get_yearly_projection_with_cost(
    meter_id: int = Query(..., description="Zähler ID"),
    year: int = Query(..., description="Jahr für das die Hochrechnung erstellt wird"),
    as_of_date: date | None = Query(
        None,
        description=(
            "Referenzdatum 'heute', bestimmt den aktiven Tarif und das "
            "Ende des bisherigen Verbrauchszeitraums. "
            "Falls nicht angegeben: Server-Datum (date.today())."
        ),
    ),
    db: Session = Depends(get_database_session),
) -> schemas.YearlyProjectionWithCostResponse:
    """Calculate yearly projection with estimated cost.
    
    Combines the annual consumption projection with cost calculation:
    1. Gets projected annual consumption from ProjectionService
    2. Determines tariff active on as_of_date (tariff_kind="consumption")
    3. Calculates actual cost from Jan 1 to as_of_date using existing cost logic
    4. Estimates projected annual cost using projected consumption and active tariff
    
    Edge cases:
    - No active tariff → projected_annual_cost = null with message
    - No projection possible (insufficient_data) → projected_annual_cost = null
    - Meter not found → 404
    - Invalid year → 422
    """
    if as_of_date is None:
        as_of_date = datetime.now(UTC).date()
    
    # 1. Get projection from ProjectionService
    try:
        projection_data = ProjectionService.calculate_projection(
            db=db,
            meter_id=meter_id,
            year=year,
            as_of_date=as_of_date,
        )
    except ValueError as e:
        error_msg = str(e)
        if "Meter mit ID" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        elif "Jahr" in error_msg:
            raise HTTPException(status_code=422, detail=error_msg)
        else:
            # Unexpected validation error
            raise HTTPException(status_code=422, detail=error_msg)
    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors (database errors, etc.)
        raise HTTPException(
            status_code=500, 
            detail=f"Interner Serverfehler: {e!s}"
        )
    
    # 2. Get active tariff for as_of_date
    active_tariff = _get_active_tariff_for_date(
        db=db,
        meter_id=meter_id,
        tariff_kind=models.TariffKind.CONSUMPTION,
        target_date=as_of_date,
    )
    
    # 3. Calculate actual cost to date (Jan 1 of year to as_of_date)
    actual_cost_to_date = None
    try:
        year_start = date(year, 1, 1)
        
        # Use existing cost calculation logic for actual cost
        if as_of_date > year_start:
            # For ongoing years, use projection-like boundary reading logic
            # This ensures consistency with projection's actual_consumption_to_date
            boundary_readings = _get_boundary_readings_for_yearly_cost(
                db, meter_id, year, as_of_date
            )
            
            if boundary_readings[0] is not None and boundary_readings[1] is not None:
                start_reading, end_reading = boundary_readings
                total_consumption = end_reading.value - start_reading.value
                _raise_if_negative(total_consumption)
                
                # Calculate the actual period covered by the readings
                reading_start_date = start_reading.reading_date
                reading_end_date = end_reading.reading_date
                total_days = (reading_end_date - reading_start_date).days
                
                if total_days > 0:
                    # Calculate overlap with Jan 1 to as_of_date period
                    cost_start_date = max(year_start, reading_start_date)
                    cost_end_date = min(as_of_date, reading_end_date)
                    
                    # Prorate consumption based on overlap days
                    overlap_days = (cost_end_date - cost_start_date).days
                    if overlap_days > 0:
                        prorated_consumption = total_consumption * Decimal(overlap_days) / Decimal(total_days)
                        
                        # Get tariffs covering the period
                        tariffs_period = _get_overlapping_tariffs(
                            db, meter_id, models.TariffKind.CONSUMPTION, cost_start_date, cost_end_date
                        )
                        
                        # Calculate cost using existing multi-period logic
                        _, total_cost, _ = _compute_cost_fields_multiperiod(
                            prorated_consumption, tariffs_period, cost_start_date, cost_end_date
                        )
                        actual_cost_to_date = total_cost
    except HTTPException:
        # If no readings or no tariff for the period, actual_cost_to_date remains None
        # This is acceptable - we still return projection data
        pass
    except ValueError:
        # Log but don't fail the whole request
        # actual_cost_to_date remains None
        pass
    
    # 4. Calculate projected annual cost if we have projection
    projected_annual_cost = None
    message = None
    
    if (
        projection_data["projected_annual_consumption"] is not None
        and projection_data["basis"] != "insufficient_data"
    ):
        # Determine which tariff to use based on year status
        year_status = ProjectionService.analyze_year_status(year, as_of_date)
        
        if year_status == "completed":
            # For completed years, calculate cost for the full year
            # using tariffs covering the year, not tariff active on as_of_date
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            
            try:
                # Get tariffs covering the full year
                tariffs_year = _get_overlapping_tariffs(
                    db, meter_id, models.TariffKind.CONSUMPTION, year_start, year_end
                )
                
                # Calculate cost for the full year
                projected_consumption = projection_data["projected_annual_consumption"]
                _, total_cost, _ = _compute_cost_fields_multiperiod(
                    projected_consumption, tariffs_year, year_start, year_end
                )
                projected_annual_cost = total_cost
            except (HTTPException, ValueError):
                # No tariff covering the full year
                message = "Kein Tarif für das gesamte Jahr gefunden."
        else:
            # For ongoing or future years, use tariff active on as_of_date
            if active_tariff is not None:
                # Calculate projected cost for full year using active tariff
                projected_consumption = projection_data["projected_annual_consumption"]
                price_per_unit = active_tariff.price_per_unit
                base_fee_monthly = (
                    active_tariff.base_fee_monthly
                    if active_tariff.base_fee_monthly is not None
                    else Decimal(0)
                )
                
                # Energy cost: projected_consumption * price_per_unit
                energy_cost = projected_consumption * price_per_unit
                
                # Base fee for full year: base_fee_monthly * 12
                # Use proper rounding at output boundary
                base_fee_annual_raw = base_fee_monthly * Decimal(12)
                total_cost_raw = energy_cost + base_fee_annual_raw
                projected_annual_cost = total_cost_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
            else:
                message = "Kein aktiver Tarif für dieses Datum gefunden."
    elif projection_data["basis"] == "insufficient_data":
        message = projection_data.get("message")
    
    # Combine projection data with cost calculations
    return schemas.YearlyProjectionWithCostResponse(
        meter_id=meter_id,
        year=year,
        unit=projection_data["unit"],
        as_of_date=as_of_date,
        actual_consumption_to_date=projection_data["actual_consumption_to_date"],
        projected_annual_consumption=projection_data["projected_annual_consumption"],
        basis=projection_data["basis"],
        actual_cost_to_date=actual_cost_to_date,
        projected_annual_cost=projected_annual_cost,
        message=message,
    )