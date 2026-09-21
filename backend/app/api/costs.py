import calendar
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..models.advance_payment import AdvancePaymentCategory
from ..services.meter_chain import get_meter_chain
from ..services.projection import ProjectionService
from .deps import get_database_session

router = APIRouter()

# Money is rounded once, at the response boundary (never on intermediate
# values, per AGENTS.md).
_CENT = Decimal("0.01")


def _prorate_monthly(
    monthly_amount: Decimal, inclusive_start: date, exclusive_end: date,
) -> Decimal:
    """Prorate a monthly amount over an inclusive-start, exclusive-end date range using
    calendar-accurate month lengths. Full months count as 1 each; partial months are
    prorated by the actual number of days in that month.
    """
    if monthly_amount == Decimal(0) or inclusive_start >= exclusive_end:
        return Decimal(0)

    total = Decimal(0)
    current = inclusive_start

    while current < exclusive_end:
        month_len = calendar.monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, month_len)
        period_end = min(month_end + timedelta(days=1), exclusive_end)

        period_days = (period_end - current).days
        if period_days <= 0:
            break

        if current.day == 1 and period_end == month_end + timedelta(days=1):
            total += monthly_amount
        else:
            total += monthly_amount * Decimal(period_days) / Decimal(month_len)

        current = period_end

    return total

# Gas meters record consumption in m³ but gas contracts bill in €/kWh;
# the missing conversion factors are a data quality error surfaced wherever
# a cost is computed for a gas meter.
_GAS_CONVERSION_FIELDS_MESSAGE = (
    "Gastarife benötigen die Felder gas_z_zahl und "
    "gas_brennwert zur Umrechnung von m³ in kWh."
)




def _combine_messages(*messages: str | None) -> str | None:
    """Combine non-empty messages into a single one, deduplicating identical entries.

    The yearly-projection response has one `message` field, but the
    actual-cost and projected-cost paths can fail independently with
    different reasons. Messages are joined with a single space; each keeps
    its own trailing period. Identical messages (e.g. both paths failing on
    missing gas conversion factors) are shown only once.
    """
    seen: set[str] = set()
    parts: list[str] = []
    for message in messages:
        if message is None or not message.strip():
            continue
        if message in seen:
            continue
        seen.add(message)
        parts.append(message)
    return " ".join(parts) if parts else None


def _raise_if_from_after_to(from_: date, to: date) -> None:
    if from_ > to:
        raise HTTPException(
            status_code=422,
            detail="Ungültiger Zeitraum: 'from' muss kleiner oder gleich 'to' sein.",
        )


def _get_boundary_readings(
    db: Session, meter_id: int, from_: date, to: date,
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
    db: Session, meter_id: int, year: int, as_of_date: date,
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
            models.Reading.reading_date == prev_year_end,
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
                models.Reading.reading_date <= as_of_date,
            )
            .order_by(models.Reading.reading_date.asc())
            .first()
        )

    # End reading: last reading <= as_of_date
    end_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date <= as_of_date,
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
    consumption: Decimal, tariff: models.TariffPeriod, from_: date, to: date,
) -> tuple[Decimal, Decimal]:
    """Compute (base_fee_total, total_cost) for a single tariff period.

    Base fee is prorated by calendar-accurate month lengths; money is
    rounded once at the output boundary (AGENTS.md).
    """
    # A null base_fee_monthly is treated as 0.
    base_fee_monthly = (
        tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
    )
    base_fee_total_raw = _prorate_monthly(base_fee_monthly, from_, to)

    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total_cost = (consumption * tariff.price_per_unit + base_fee_total_raw).quantize(
        _CENT, rounding=ROUND_HALF_UP,
    )
    return base_fee_total, total_cost


def _compute_cost_fields_multiperiod(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (base_fee_total, total_cost, first_price_per_unit) for multiple periods.

    Consumption is allocated proportionally by overlapping days in each period.
    Base fee is prorated by calendar-accurate month lengths; money is
    rounded once at the output boundary (AGENTS.md).

    For gas meters (meter_type=MeterType.GAS) the per-period consumption
    share (m³) is converted to kWh with that period's own conversion
    factors BEFORE applying price_per_unit:
        kWh = m³ * gas_z_zahl (Zustandszahl) * gas_brennwert (kWh/m³)
    Both fields are required on every overlapping gas tariff period; a
    missing value raises a 422. Non-gas meters pass meter_type=None and
    are completely unaffected.

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

        # Gas meters record consumption in m³ but gas contracts bill in
        # €/kWh: convert this period's share with its own factors.
        if meter_type == models.MeterType.GAS:
            if tariff.gas_z_zahl is None or tariff.gas_brennwert is None:
                raise HTTPException(
                    status_code=422,
                    detail=_GAS_CONVERSION_FIELDS_MESSAGE,
                )
            consumption_in_period = (
                consumption_in_period * tariff.gas_z_zahl * tariff.gas_brennwert
            )

        # A null base_fee_monthly is treated as 0.
        base_fee_monthly = (
            tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
        )
        base_fee_total_raw += _prorate_monthly(base_fee_monthly, period_start, period_end)
        energy_cost_raw += consumption_in_period * tariff.price_per_unit

    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total_cost = (energy_cost_raw + base_fee_total_raw).quantize(_CENT, rounding=ROUND_HALF_UP)

    # Return first period's price for backward compatibility
    first_price_per_unit = tariffs[0].price_per_unit

    return base_fee_total, total_cost, first_price_per_unit


# ---------------------------------------------------------------------------
# Meter-chain consumption helpers
# ---------------------------------------------------------------------------


def _get_chain_consumption(
    db: Session,
    chain: list[models.Meter],
    from_: date,
    to: date,
) -> tuple[Decimal, list[tuple[models.Meter, date, date, Decimal]]]:
    """Compute total consumption across a meter replacement chain.

    For a chain [G, P, M] (oldest → newest) the total consumption over
    [from_, to] is the sum of each meter's contribution over its own
    active segment within [from_, to].

    Segment boundaries are determined by the **first** reading of each
    successor meter: the predecessor's segment ends the day before, the
    successor's segment starts on that day.

    Returns:
        (total_consumption, segments) where each segment is
        (meter, seg_from, seg_to_exclusive, consumption_on_segment).
        seg_to_exclusive follows inclusive-exclusive convention used
        internally (consistent with _compute_cost_fields_multiperiod).

    Raises HTTPException 404 when no readings are found anywhere in the
    chain for the requested range.

    """
    segments: list[tuple[models.Meter, date, date, Decimal]] = []
    total_consumption = Decimal(0)

    # Determine the transition dates from each predecessor to its successor.
    # transition_dates[i] = first reading date of chain[i+1] (the successor)
    # which defines the handover point.
    transition_dates: list[date] = []
    for i in range(1, len(chain)):
        successor = chain[i]
        first_successor_reading = (
            db.query(models.Reading)
            .filter(models.Reading.meter_id == successor.id)
            .order_by(models.Reading.reading_date.asc())
            .first()
        )
        if first_successor_reading is None:
            # Successor has no readings at all — treat the entire range as
            # belonging to the predecessor (no transition happens in practice).
            transition_dates.append(date.max)
        else:
            transition_dates.append(first_successor_reading.reading_date)

    any_reading_found = False

    for idx, meter in enumerate(chain):
        # Determine the date segment for this meter within [from_, to].
        seg_from = from_
        if idx < len(transition_dates):
            # This meter's segment ends the day before the successor's first reading.
            seg_to = min(to, transition_dates[idx] - timedelta(days=1))
        else:
            # Last meter in the chain — extends to the end of the requested range.
            seg_to = to

        # Also constrain seg_from: if this is not the first meter in the chain,
        # its segment starts at the transition from the previous meter.
        if idx > 0:
            seg_from = max(from_, transition_dates[idx - 1])

        if seg_from > seg_to:
            # This meter has no active segment within [from_, to] — skip.
            continue

        # Find readings for this meter within its segment.
        seg_start_reading = (
            db.query(models.Reading)
            .filter(
                models.Reading.meter_id == meter.id,
                models.Reading.reading_date >= seg_from,
                models.Reading.reading_date <= seg_to,
            )
            .order_by(models.Reading.reading_date.asc())
            .first()
        )
        seg_end_reading = (
            db.query(models.Reading)
            .filter(
                models.Reading.meter_id == meter.id,
                models.Reading.reading_date <= seg_to,
            )
            .order_by(models.Reading.reading_date.desc())
            .first()
        )

        if seg_start_reading is None or seg_end_reading is None:
            # No readings for this meter in its segment — skip.
            continue

        if seg_end_reading.reading_date < seg_start_reading.reading_date:
            continue

        if seg_end_reading.reading_date == seg_start_reading.reading_date:
            # Only one distinct date — no consumption calculable for this segment.
            continue

        any_reading_found = True
        seg_consumption = seg_end_reading.value - seg_start_reading.value
        _raise_if_negative(seg_consumption)

        # Store segment with inclusive-exclusive dates for cost allocation
        # (seg_start_reading.reading_date inclusive, seg_end_reading.reading_date exclusive)
        segments.append((
            meter,
            seg_start_reading.reading_date,
            seg_end_reading.reading_date,
            seg_consumption,
        ))
        total_consumption += seg_consumption

    if not any_reading_found:
        raise HTTPException(
            status_code=404,
            detail="Kein Zählerstand im angegebenen Zeitraum gefunden.",
        )

    return total_consumption, segments


def _compute_chain_cost(
    db: Session,
    chain: list[models.Meter],
    segments: list[tuple[models.Meter, date, date, Decimal]],
    tariff_kind: models.TariffKind,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (base_fee_total, total_cost, first_price_per_unit) for a chain of segments.

    Each segment is costed against the tariff for that specific meter, so
    tariff lookups happen per-meter in the chain. Tariffs are looked up on
    the meter that generated the readings, not on the "current" meter.

    Returns the first overlapping tariff's price_per_unit (of the oldest
    meter segment) for backward compatibility in API responses.
    """
    base_fee_total_raw = Decimal(0)
    energy_cost_raw = Decimal(0)
    first_price_per_unit: Decimal | None = None

    for meter, seg_from, seg_to, seg_consumption in segments:
        tariffs = _get_overlapping_tariffs(db, meter.id, tariff_kind, seg_from, seg_to)
        if first_price_per_unit is None:
            first_price_per_unit = tariffs[0].price_per_unit

        # Accumulate unrounded base fee and energy cost across segments so that
        # rounding happens only once at the final output boundary (AGENTS.md).
        _seg_base_raw, _seg_energy_raw = _compute_cost_fields_multiperiod_raw(
            seg_consumption, tariffs, seg_from, seg_to, meter_type=meter.meter_type,
        )
        base_fee_total_raw += _seg_base_raw
        energy_cost_raw += _seg_energy_raw

    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total_cost = (energy_cost_raw + base_fee_total_raw).quantize(_CENT, rounding=ROUND_HALF_UP)

    if first_price_per_unit is None:
        # No segments were processed — should not happen but guard defensively.
        raise HTTPException(
            status_code=404,
            detail="Kein gültiger Tarif für diesen Zeitraum gefunden.",
        )

    return base_fee_total, total_cost, first_price_per_unit


def _compute_cost_fields_multiperiod_raw(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal]:
    """Like _compute_cost_fields_multiperiod but returns (base_fee_raw, energy_cost_raw)
    without rounding, for accumulation across chain segments.
    """
    total_days = Decimal((to - from_).days)
    if total_days == 0:
        total_days = Decimal("0.000001")

    base_fee_total_raw = Decimal(0)
    energy_cost_raw = Decimal(0)

    for tariff in tariffs:
        period_start = max(from_, tariff.valid_from)
        period_end = to
        if tariff.valid_to is not None:
            period_end = min(to, tariff.valid_to + timedelta(days=1))

        overlap_days = Decimal((period_end - period_start).days)
        if overlap_days <= 0:
            continue

        consumption_in_period = consumption * overlap_days / total_days

        if meter_type == models.MeterType.GAS:
            if tariff.gas_z_zahl is None or tariff.gas_brennwert is None:
                raise HTTPException(
                    status_code=422,
                    detail=_GAS_CONVERSION_FIELDS_MESSAGE,
                )
            consumption_in_period = (
                consumption_in_period * tariff.gas_z_zahl * tariff.gas_brennwert
            )

        base_fee_monthly = (
            tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
        )
        base_fee_total_raw += _prorate_monthly(base_fee_monthly, period_start, period_end)
        energy_cost_raw += consumption_in_period * tariff.price_per_unit

    return base_fee_total_raw, energy_cost_raw


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

    chain = get_meter_chain(db, meter_id)
    meter = chain[-1]  # the requested (newest) meter

    if len(chain) == 1:
        # Fast path: no replacement chain, use original logic unchanged.
        start_reading, end_reading = _get_boundary_readings(db, meter_id, from_, to)
        consumption = end_reading.value - start_reading.value
        _raise_if_negative(consumption)

        tariffs = _get_overlapping_tariffs(
            db, meter_id, models.TariffKind.CONSUMPTION, from_, to,
        )
        base_fee_total, total_cost, price_per_unit = _compute_cost_fields_multiperiod(
            consumption, tariffs, from_, to, meter_type=meter.meter_type,
        )
    else:
        # Chain path: follow the replacement chain.
        total_consumption, segments = _get_chain_consumption(db, chain, from_, to)
        base_fee_total, total_cost, price_per_unit = _compute_chain_cost(
            db, chain, segments, models.TariffKind.CONSUMPTION,
        )
        consumption = total_consumption

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

    # Cold water consumption — chain-aware
    cold_chain = get_meter_chain(db, water_cold_meter_id)
    cold_meter = cold_chain[-1]

    if len(cold_chain) == 1:
        start_reading, end_reading = _get_boundary_readings(
            db, water_cold_meter_id, from_, to,
        )
        cold_consumption = end_reading.value - start_reading.value
        _raise_if_negative(cold_consumption)
    else:
        cold_consumption, _cold_segments = _get_chain_consumption(
            db, cold_chain, from_, to,
        )

    # If the garden meter parameter is provided but has no readings in
    # the range, this IS an error (same lookup logic as above): the
    # client explicitly claimed this meter is relevant. Only omitting
    # the parameter entirely triggers the "= 0" fallback.
    garden_consumption = Decimal(0)
    if water_garden_meter_id is not None:
        garden_chain = get_meter_chain(db, water_garden_meter_id)
        if len(garden_chain) == 1:
            garden_start, garden_end = _get_boundary_readings(
                db, water_garden_meter_id, from_, to,
            )
            garden_consumption = garden_end.value - garden_start.value
        else:
            garden_consumption, _ = _get_chain_consumption(
                db, garden_chain, from_, to,
            )
        # A garden consumption exceeding the cold consumption is a data
        # quality issue that is not validated here; the wastewater
        # consumption is simply floored at 0.
    wastewater_consumption = max(Decimal(0), cold_consumption - garden_consumption)

    # The wastewater tariff is attached to the cold-water meter (newest in chain).
    if len(cold_chain) == 1:
        tariffs = _get_overlapping_tariffs(
            db, water_cold_meter_id, models.TariffKind.WASTEWATER, from_, to,
        )
        base_fee_total, total_cost, price_per_unit = _compute_cost_fields_multiperiod(
            wastewater_consumption, tariffs, from_, to,
        )
    else:
        # For a chain, use the tariff segments aligned with the cold meter chain
        _, cold_segments = _get_chain_consumption(db, cold_chain, from_, to)
        # Recalculate segments with wastewater_consumption proportionally distributed
        base_fee_total, total_cost, price_per_unit = _compute_chain_cost(
            db,
            cold_chain,
            # Re-weight: distribute wastewater_consumption over same date segments
            # but we need the segments with the correct dates. We reuse cold_segments
            # for date boundaries but recalculate consumption proportionally.
            _rescale_segments(cold_segments, cold_consumption, wastewater_consumption),
            models.TariffKind.WASTEWATER,
        )

    return schemas.WastewaterCostCalculationResponse(
        water_cold_meter_id=water_cold_meter_id,
        water_garden_meter_id=water_garden_meter_id,
        from_date=from_,
        to_date=to,
        cold_consumption=cold_consumption,
        garden_consumption=garden_consumption,
        wastewater_consumption=wastewater_consumption,
        unit=cold_meter.unit,
        price_per_unit=price_per_unit,
        base_fee_total=base_fee_total,
        total_cost=total_cost,
    )


def _rescale_segments(
    segments: list[tuple[models.Meter, date, date, Decimal]],
    original_total: Decimal,
    new_total: Decimal,
) -> list[tuple[models.Meter, date, date, Decimal]]:
    """Rescale segment consumptions proportionally to new_total.

    Used to distribute wastewater consumption (= cold - garden) across the
    same meter segments and date ranges as the cold consumption, preserving
    the proportional split.
    """
    if original_total == 0:
        # All segments get 0 consumption
        return [(m, f, t, Decimal(0)) for m, f, t, _ in segments]
    return [
        (m, f, t, cons * new_total / original_total)
        for m, f, t, cons in segments
    ]


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
    - Actual cost unavailable (no tariff for the period, negative
      consumption, gas factors missing) → actual_cost_to_date = null with
      message; if the projected path also fails, both reasons are combined
      into the single message field (deduplicated)
    - Gas meter with tariff lacking gas_z_zahl/gas_brennwert → cost fields
      null with explanatory message (200, same as "no active tariff")
    - Meter not found → 404
    - Invalid year → 422
    """
    if as_of_date is None:
        as_of_date = datetime.now(UTC).date()

    # Build chain for chain-aware projection (chain[-1] is the requested meter)
    chain = get_meter_chain(db, meter_id)

    # 1. Get projection from ProjectionService (chain-aware)
    try:
        projection_data = ProjectionService.calculate_projection(
            db=db,
            meter_id=meter_id,
            year=year,
            as_of_date=as_of_date,
            chain=chain,
        )
    except ValueError as e:
        error_msg = str(e)
        if "Meter mit ID" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        if "Jahr" in error_msg:
            raise HTTPException(status_code=422, detail=error_msg)
        # Unexpected validation error
        raise HTTPException(status_code=422, detail=error_msg)
    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors (database errors, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"Interner Serverfehler: {e!s}",
        )

    # 2. Get active tariff for as_of_date
    active_tariff = _get_active_tariff_for_date(
        db=db,
        meter_id=meter_id,
        tariff_kind=models.TariffKind.CONSUMPTION,
        target_date=as_of_date,
    )

    # Meter type is needed for the gas m³→kWh conversion in the cost
    # calculations below. The meter is guaranteed to exist because
    # ProjectionService already validated it above.
    meter = chain[-1]

    # 3. Calculate actual cost to date (Jan 1 of year to as_of_date)
    actual_cost_to_date = None
    actual_cost_message = None
    try:
        year_start = date(year, 1, 1)

        # Use existing cost calculation logic for actual cost
        if as_of_date > year_start:
            # For ongoing years, use projection-like boundary reading logic
            # This ensures consistency with projection's actual_consumption_to_date
            boundary_readings = _get_boundary_readings_for_yearly_cost(
                db, meter_id, year, as_of_date,
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
                            db, meter_id, models.TariffKind.CONSUMPTION, cost_start_date, cost_end_date,
                        )

                        # Calculate cost using existing multi-period logic
                        _, total_cost, _ = _compute_cost_fields_multiperiod(
                            prorated_consumption,
                            tariffs_period,
                            cost_start_date,
                            cost_end_date,
                            meter_type=meter.meter_type,
                        )
                        actual_cost_to_date = total_cost
    except HTTPException as e:
        # The actual cost is not available (e.g. no tariff covering the
        # period, negative consumption, or gas conversion factors missing).
        # Surface the reason instead of silently returning null.
        actual_cost_message = str(e.detail)
    except ValueError:
        # Unexpected non-HTTP error: log-worthy, actual_cost_to_date remains
        # None without a user-facing message.
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
                    db, meter_id, models.TariffKind.CONSUMPTION, year_start, year_end,
                )

                # Calculate cost for the full year
                projected_consumption = projection_data["projected_annual_consumption"]
                _, total_cost, _ = _compute_cost_fields_multiperiod(
                    projected_consumption,
                    tariffs_year,
                    year_start,
                    year_end,
                    meter_type=meter.meter_type,
                )
                projected_annual_cost = total_cost
            except HTTPException as e:
                if e.status_code == 422:
                    # Gas conversion factors missing on an applicable tariff.
                    message = str(e.detail)
                else:
                    # No tariff covering the full year
                    message = "Kein Tarif für das gesamte Jahr gefunden."
            except ValueError:
                # No tariff covering the full year
                message = "Kein Tarif für das gesamte Jahr gefunden."
        # For ongoing or future years, use tariff active on as_of_date
        elif active_tariff is not None:
            projected_consumption = projection_data["projected_annual_consumption"]
            price_per_unit = active_tariff.price_per_unit
            base_fee_monthly = (
                active_tariff.base_fee_monthly
                if active_tariff.base_fee_monthly is not None
                else Decimal(0)
            )

            # Gas meters record consumption in m³ but gas contracts bill
            # in €/kWh: convert the projected consumption with the active
            # tariff's own conversion factors BEFORE applying
            # price_per_unit (same rule as _compute_cost_fields_multiperiod).
            if (
                meter.meter_type == models.MeterType.GAS
                and (
                    active_tariff.gas_z_zahl is None
                    or active_tariff.gas_brennwert is None
                )
            ):
                message = _GAS_CONVERSION_FIELDS_MESSAGE
            else:
                if meter.meter_type == models.MeterType.GAS:
                    projected_consumption = (
                        projected_consumption
                        * active_tariff.gas_z_zahl
                        * active_tariff.gas_brennwert
                    )

                # Energy cost: projected_consumption * price_per_unit
                energy_cost = projected_consumption * price_per_unit

                # Base fee for full year: base_fee_monthly * 12
                # Use proper rounding at output boundary
                base_fee_annual_raw = base_fee_monthly * Decimal(12)
                total_cost_raw = energy_cost + base_fee_annual_raw
                projected_annual_cost = total_cost_raw.quantize(
                    _CENT, rounding=ROUND_HALF_UP,
                )
        else:
            message = "Kein aktiver Tarif für dieses Datum gefunden."
    elif projection_data["basis"] == "insufficient_data":
        message = projection_data.get("message")

    # Combine failures from the actual-cost path (if any) with the
    # projected-cost/insufficient-data message (if any). Deduplication
    # prevents e.g. the gas-factors message appearing twice when both paths
    # fail on the same tariff.
    message = _combine_messages(actual_cost_message, message)

    # Combine projection data with cost calculations
    return schemas.YearlyProjectionWithCostResponse(
        meter_id=meter_id,
        year=year,
        unit=projection_data["unit"],
        as_of_date=as_of_date,
        actual_consumption_to_date=projection_data["actual_consumption_to_date"],
        projected_annual_consumption=projection_data["projected_annual_consumption"],
        projected_meter_reading_end_of_year=projection_data["projected_meter_reading_end_of_year"],
        start_reading_value=projection_data.get("start_reading_value"),
        start_reading_date=projection_data.get("start_reading_date"),
        basis=projection_data["basis"],
        actual_cost_to_date=actual_cost_to_date,
        projected_annual_cost=projected_annual_cost,
        message=message,
    )


def _compute_total_advance_payments(
    db: Session, meter_id: int, year: int,
) -> tuple[Decimal, bool]:
    """Sum the advance payments for a meter overlapping a year, prorated by days.
    Uses meter_id for non-wastewater categories.
    """
    return _compute_total_advance_payments_by_column(
        db, models.AdvancePayment.meter_id, meter_id, year,
    )


def _compute_total_advance_payments_by_column(
    db: Session,
    column,
    value: int,
    year: int,
) -> tuple[Decimal, bool]:
    """Generic advance payment sum prorated by days, filtering by an arbitrary
    FK column (meter_id or water_cold_meter_id).
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    payments = (
        db.query(models.AdvancePayment)
        .filter(
            column == value,
            models.AdvancePayment.valid_from <= year_end,
            or_(
                models.AdvancePayment.valid_to.is_(None),
                models.AdvancePayment.valid_to >= year_start,
            ),
        )
        .order_by(models.AdvancePayment.valid_from.asc())
        .all()
    )

    if not payments:
        return Decimal(0), False

    total_raw = Decimal(0)
    for payment in payments:
        overlap_start = max(year_start, payment.valid_from)
        overlap_end = year_end
        if payment.valid_to is not None:
            overlap_end = min(year_end, payment.valid_to)
        if overlap_start > overlap_end:
            continue
        total_raw += _prorate_monthly(
            payment.monthly_amount, overlap_start, overlap_end + timedelta(days=1),
        )

    total = total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    return total, True


def _compute_yearly_cost_for_diff(
    db: Session,
    meter_id: int,
    year: int,
    as_of_date: date,
    chain: list[models.Meter],
) -> tuple[Decimal | None, Literal["actual", "projected"] | None, str | None]:
    """Compute the estimated/actual annual cost for the advance-payment diff.

    Reuses the same rules as the yearly-projection cost:
    - Completed year: full-year cost from the tariffs covering the year
      (basis "actual").
    - Ongoing/future year: projected cost using the tariff active on
      as_of_date (basis "projected").
    - No projection possible / missing tariff / missing gas factors: the
      cost stays None and the reason is returned in the message.

    Returns (cost, cost_basis, message). Cost is already rounded and
    returned as a Decimal; message is None on success.
    """
    # Validate year and meter (chain is built before, so the meter exists).
    try:
        ProjectionService.validate_year(year)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        projection_data = ProjectionService.calculate_projection(
            db=db,
            meter_id=meter_id,
            year=year,
            as_of_date=as_of_date,
            chain=chain,
        )
    except ValueError as e:
        error_msg = str(e)
        if "Meter mit ID" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=422, detail=error_msg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Interner Serverfehler: {e!s}",
        )

    meter = chain[-1]

    if (
        projection_data["projected_annual_consumption"] is None
        or projection_data["basis"] == "insufficient_data"
    ):
        return None, None, projection_data.get("message") or "Unzureichende Daten für die Hochrechnung."

    year_status = ProjectionService.analyze_year_status(year, as_of_date)
    projected_consumption = projection_data["projected_annual_consumption"]

    if year_status == "completed":
        # Full year cost with the tariffs covering the whole year; for a
        # completed year the projected consumption IS the actual one.
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        try:
            tariffs_year = _get_overlapping_tariffs(
                db, meter_id, models.TariffKind.CONSUMPTION, year_start, year_end,
            )
            _, total_cost, _ = _compute_cost_fields_multiperiod(
                projected_consumption,
                tariffs_year,
                year_start,
                year_end,
                meter_type=meter.meter_type,
            )
            return total_cost, "actual", None
        except HTTPException as e:
            if e.status_code == 422:
                return None, None, str(e.detail)
            return None, None, str(e.detail)
        except ValueError:
            return None, None, "Kein Tarif für das gesamte Jahr gefunden."
    else:
        # Ongoing or future year: projected cost with the tariff active on
        # as_of_date (same rules as the yearly-projection endpoint).
        active_tariff = _get_active_tariff_for_date(
            db=db,
            meter_id=meter_id,
            tariff_kind=models.TariffKind.CONSUMPTION,
            target_date=as_of_date,
        )
        if active_tariff is None:
            return None, None, "Kein aktiver Tarif für dieses Datum gefunden."

        price_per_unit = active_tariff.price_per_unit
        base_fee_monthly = (
            active_tariff.base_fee_monthly
            if active_tariff.base_fee_monthly is not None
            else Decimal(0)
        )

        if (
            meter.meter_type == models.MeterType.GAS
            and (
                active_tariff.gas_z_zahl is None
                or active_tariff.gas_brennwert is None
            )
        ):
            return None, None, _GAS_CONVERSION_FIELDS_MESSAGE

        if meter.meter_type == models.MeterType.GAS:
            projected_consumption = (
                projected_consumption
                * active_tariff.gas_z_zahl
                * active_tariff.gas_brennwert
            )

        energy_cost = projected_consumption * price_per_unit
        base_fee_annual_raw = base_fee_monthly * Decimal(12)
        total_cost = (energy_cost + base_fee_annual_raw).quantize(
            _CENT, rounding=ROUND_HALF_UP,
        )
        return total_cost, "projected", None


def _get_boundary_readings_for_wastewater(
    db: Session, meter_id: int, from_: date, to: date,
) -> tuple[models.Reading, models.Reading]:
    """Return (start, end) readings for consumption over [from_, to].

    Start: reading with the largest reading_date <= from_ (reading just before
    or on the start date). End: reading with the largest reading_date <= to.
    Raises 404 if no readings are found.
    """
    start_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date <= from_,
        )
        .order_by(models.Reading.reading_date.desc())
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
            detail="Kein Zählerstand für die Verbrauchsberechnung gefunden.",
        )
    return start_reading, end_reading


def _compute_wastewater_consumption(
    db: Session,
    water_cold_meter_id: int,
    water_garden_meter_id: int | None,
    from_: date,
    to: date,
) -> Decimal:
    """Compute wastewater consumption = cold_water_consumption - garden_water_consumption.

    garden_water_consumption is 0 if water_garden_meter_id is None.
    The result is floored at 0.
    """
    cold_chain = get_meter_chain(db, water_cold_meter_id)
    if len(cold_chain) == 1:
        start_reading, end_reading = _get_boundary_readings_for_wastewater(
            db, water_cold_meter_id, from_, to,
        )
        cold_consumption = end_reading.value - start_reading.value
        _raise_if_negative(cold_consumption)
    else:
        cold_consumption, _cold_segments = _get_chain_consumption(db, cold_chain, from_, to)

    garden_consumption = Decimal(0)
    if water_garden_meter_id is not None:
        garden_chain = get_meter_chain(db, water_garden_meter_id)
        if len(garden_chain) == 1:
            garden_start, garden_end = _get_boundary_readings_for_wastewater(
                db, water_garden_meter_id, from_, to,
            )
            garden_consumption = garden_end.value - garden_start.value
        else:
            garden_consumption, _ = _get_chain_consumption(db, garden_chain, from_, to)

    return max(Decimal(0), cold_consumption - garden_consumption)


def _compute_yearly_wastewater_cost_for_diff(
    db: Session,
    water_cold_meter_id: int,
    year: int,
    as_of_date: date,
    chain: list[models.Meter],
    water_garden_meter_id: int | None = None,
) -> tuple[Decimal | None, Literal["actual", "projected"] | None, str | None]:
    """Compute the annual wastewater cost for the advance-payment diff.

    Uses _compute_wastewater_consumption to get the net wastewater volume,
    then applies the WASTEWATER tariff.
    """
    try:
        ProjectionService.validate_year(year)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    try:
        wastewater_consumption = _compute_wastewater_consumption(
            db, water_cold_meter_id, water_garden_meter_id, year_start, year_end,
        )
    except HTTPException:
        return None, None, "Kein Zählerstand für die Schmutzwasserberechnung gefunden."

    year_status = ProjectionService.analyze_year_status(year, as_of_date)

    try:
        if year_status == "completed":
            tariffs = _get_overlapping_tariffs(
                db, water_cold_meter_id, models.TariffKind.WASTEWATER, year_start, year_end,
            )
            _base_fee, total_cost, _price = _compute_cost_fields_multiperiod(
                wastewater_consumption, tariffs, year_start, year_end,
            )
            return total_cost, "actual", None
        active_tariff = _get_active_tariff_for_date(
            db=db,
            meter_id=water_cold_meter_id,
            tariff_kind=models.TariffKind.WASTEWATER,
            target_date=as_of_date,
        )
        if active_tariff is None:
            return None, None, "Kein aktiver Schmutzwassertarif für dieses Datum gefunden."

        price_per_unit = active_tariff.price_per_unit
        base_fee_monthly = (
            active_tariff.base_fee_monthly
            if active_tariff.base_fee_monthly is not None
            else Decimal(0)
        )
        energy_cost = wastewater_consumption * price_per_unit
        base_fee_annual_raw = base_fee_monthly * Decimal(12)
        total_cost = (energy_cost + base_fee_annual_raw).quantize(
            _CENT, rounding=ROUND_HALF_UP,
        )
        return total_cost, "projected", None
    except HTTPException as e:
        return None, None, str(e.detail)


@router.get("/advance-payment-diff", response_model=schemas.AdvancePaymentDiffResponse)
def get_advance_payment_diff(
    meter_id: int = Query(...),
    year: int = Query(...),
    as_of_date: date | None = Query(
        None,
        description=(
            "Referenzdatum 'heute' (Standard: Server-Datum). Bestimmt, ob das "
            "Jahr als abgeschlossen ('actual') oder laufend/zukünftig "
            "('projected') bewertet wird."
        ),
    ),
    water_cold_meter_id: int | None = Query(
        None,
        description=(
            "Optional: für wastewater-Kategorie. Wenn gesetzt, wird die "
            "Schmutzwasser-Diff berechnet."
        ),
    ),
    water_garden_meter_id: int | None = Query(
        None,
        description=(
            "Optional: für wastewater-Kategorie. Wenn gesetzt, wird "
            "Gartenwasserverbrauch abgezogen."
        ),
    ),
    db: Session = Depends(get_database_session),
):
    """Calculate the difference between paid/planned advance payments and the
    estimated/actual annual cost for a meter and a year.

    For non-wastewater categories: uses the meter_id directly.
    For wastewater (water_cold_meter_id): computes the wastewater consumption
    as cold_water_consumption - garden_water_consumption and uses the
    wastewater tariff for cost calculation.

    difference = total_advance_payments - estimated_or_actual_cost
    (positive = surplus/Guthaben, negative = Nachzahlung).
    """
    if as_of_date is None:
        as_of_date = datetime.now(UTC).date()

    return _compute_advance_payment_diff(
        db=db, meter_id=meter_id, year=year, as_of_date=as_of_date,
        water_cold_meter_id=water_cold_meter_id,
        water_garden_meter_id=water_garden_meter_id,
    )


def _compute_advance_payment_diff(
    db: Session,
    meter_id: int,
    year: int,
    as_of_date: date,
    water_cold_meter_id: int | None = None,
    water_garden_meter_id: int | None = None,
) -> schemas.AdvancePaymentDiffResponse:
    is_wastewater = water_cold_meter_id is not None

    if is_wastewater:
        # Wastewater mode: 404/422 on the cold water meter
        chain = get_meter_chain(db, water_cold_meter_id)
        actual_meter_id = water_cold_meter_id
    else:
        chain = get_meter_chain(db, meter_id)
        actual_meter_id = meter_id

    # 1. Estimated/actual annual cost
    if is_wastewater:
        estimated_or_actual_cost, cost_basis, cost_message = (
            _compute_yearly_wastewater_cost_for_diff(
                db, water_cold_meter_id, year, as_of_date, chain,
                water_garden_meter_id=water_garden_meter_id,
            )
        )
    else:
        estimated_or_actual_cost, cost_basis, cost_message = (
            _compute_yearly_cost_for_diff(
                db, meter_id, year, as_of_date, chain,
            )
        )

    # 2. Total advance payments overlapping the year
    if is_wastewater:
        total_advance_payments, found = _compute_total_advance_payments_by_column(
            db, models.AdvancePayment.water_cold_meter_id, water_cold_meter_id, year,
        )
    else:
        total_advance_payments, found = _compute_total_advance_payments(db, meter_id, year)

    # 3. Difference
    difference = None
    if estimated_or_actual_cost is not None and found:
        difference = (total_advance_payments - estimated_or_actual_cost).quantize(
            _CENT, rounding=ROUND_HALF_UP,
        )

    message = _combine_messages(cost_message, None if found else "Kein Abschlag für dieses Jahr hinterlegt.")

    return schemas.AdvancePaymentDiffResponse(
        meter_id=actual_meter_id,
        year=year,
        estimated_or_actual_cost=(
            str(estimated_or_actual_cost) if estimated_or_actual_cost is not None else None
        ),
        cost_basis=cost_basis,
        total_advance_payments=str(total_advance_payments) if found else None,
        difference=str(difference) if difference is not None else None,
        message=message,
    )


@router.get(
    "/advance-payment-diff-by-category",
    response_model=schemas.AdvancePaymentDiffByCategoryResponse,
)
def get_advance_payment_diff_by_category(
    category: AdvancePaymentCategory = Query(...),
    year: int = Query(...),
    as_of_date: date | None = Query(
        None,
        description=(
            "Referenzdatum 'heute' (Standard: Server-Datum). Bestimmt, ob das "
            "Jahr als abgeschlossen ('actual') oder laufend/zukünftig "
            "('projected') bewertet wird."
        ),
    ),
    meter_id: int | None = Query(
        None,
        description="Erforderlich für Kategorien gas, cold_water, power_import.",
    ),
    water_cold_meter_id: int | None = Query(
        None,
        description="Erforderlich für Kategorie wastewater.",
    ),
    water_garden_meter_id: int | None = Query(
        None,
        description="Optional für Kategorie wastewater. Gartenwasserverbrauch wird abgezogen.",
    ),
    db: Session = Depends(get_database_session),
):
    if as_of_date is None:
        as_of_date = datetime.now(UTC).date()

    if category == AdvancePaymentCategory.WASTEWATER:
        if water_cold_meter_id is None:
            raise HTTPException(
                status_code=422,
                detail="water_cold_meter_id ist erforderlich für Kategorie wastewater.",
            )
        if meter_id is not None:
            raise HTTPException(
                status_code=422,
                detail="meter_id darf nicht gesetzt sein für Kategorie wastewater.",
            )
        result = _compute_advance_payment_diff(
            db=db, meter_id=water_cold_meter_id, year=year,
            as_of_date=as_of_date,
            water_cold_meter_id=water_cold_meter_id,
            water_garden_meter_id=water_garden_meter_id,
        )
    else:
        if meter_id is None:
            raise HTTPException(
                status_code=422,
                detail="meter_id ist erforderlich für diese Kategorie.",
            )
        if water_cold_meter_id is not None:
            raise HTTPException(
                status_code=422,
                detail="water_cold_meter_id darf nicht gesetzt sein für diese Kategorie.",
            )
        if water_garden_meter_id is not None:
            raise HTTPException(
                status_code=422,
                detail="water_garden_meter_id darf nicht gesetzt sein für diese Kategorie.",
            )
        result = _compute_advance_payment_diff(
            db=db, meter_id=meter_id, year=year, as_of_date=as_of_date,
        )

    # Add category to the response
    return schemas.AdvancePaymentDiffByCategoryResponse(
        **result.model_dump(),
        category=category,
    )


def _compute_yearly_cost_for_chain(
    db: Session,
    meter_id: int,
    year: int,
    as_of_date: date,
    chain: list[models.Meter],
) -> tuple[Decimal | None, Decimal | None, Literal["actual", "projected"] | None, str | None]:
    """Compute consumption, cost, and cost_basis for a chain + year.

    Returns (consumption, cost, cost_basis, message).
    Calls ProjectionService and cost logic, catching failures so the caller
    can handle per-year errors without crashing the whole response.
    """
    try:
        ProjectionService.validate_year(year)
    except ValueError:
        return None, None, None, None

    try:
        projection_data = ProjectionService.calculate_projection(
            db=db, meter_id=meter_id, year=year, as_of_date=as_of_date, chain=chain,
        )
    except Exception:  # noqa: BLE001
        return None, None, None, None

    meter = chain[-1]

    if (
        projection_data["projected_annual_consumption"] is None
        or projection_data["basis"] == "insufficient_data"
    ):
        return None, None, None, projection_data.get("message")

    projected_consumption = projection_data["projected_annual_consumption"]
    year_status = ProjectionService.analyze_year_status(year, as_of_date)

    if year_status == "completed":
        cost_basis: Literal["actual", "projected"] = "actual"
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        try:
            tariffs_year = _get_overlapping_tariffs(
                db, meter_id, models.TariffKind.CONSUMPTION, year_start, year_end,
            )
            _, total_cost, _ = _compute_cost_fields_multiperiod(
                projected_consumption, tariffs_year, year_start, year_end,
                meter_type=meter.meter_type,
            )
            return projected_consumption, total_cost, cost_basis, None
        except HTTPException:
            return projected_consumption, None, cost_basis, None
        except ValueError:
            return projected_consumption, None, cost_basis, None
    else:
        cost_basis = "projected"
        active_tariff = _get_active_tariff_for_date(
            db=db, meter_id=meter_id, tariff_kind=models.TariffKind.CONSUMPTION,
            target_date=as_of_date,
        )
        if active_tariff is None:
            return projected_consumption, None, cost_basis, "Kein aktiver Tarif für dieses Datum gefunden."

        price_per_unit = active_tariff.price_per_unit
        base_fee_monthly = (
            active_tariff.base_fee_monthly if active_tariff.base_fee_monthly is not None else Decimal(0)
        )

        if (
            meter.meter_type == models.MeterType.GAS
            and (active_tariff.gas_z_zahl is None or active_tariff.gas_brennwert is None)
        ):
            return projected_consumption, None, cost_basis, _GAS_CONVERSION_FIELDS_MESSAGE

        cons_for_cost = projected_consumption
        if meter.meter_type == models.MeterType.GAS:
            cons_for_cost = (
                cons_for_cost * active_tariff.gas_z_zahl * active_tariff.gas_brennwert
            )

        energy_cost = cons_for_cost * price_per_unit
        base_fee_annual_raw = base_fee_monthly * Decimal(12)
        total_cost = (energy_cost + base_fee_annual_raw).quantize(
            _CENT, rounding=ROUND_HALF_UP,
        )
        return projected_consumption, total_cost, cost_basis, None


def _get_all_reading_years_for_chain(db: Session, chain: list[models.Meter]) -> list[int]:
    """Return distinct years with at least one reading anywhere in the chain, sorted."""
    chain_ids = [m.id for m in chain]
    results = (
        db.query(func.extract("year", models.Reading.reading_date).label("year"))
        .filter(models.Reading.meter_id.in_(chain_ids))
        .distinct()
        .order_by("year")
        .all()
    )
    return [int(r.year) for r in results]


@router.get("/years-overview", response_model=list[schemas.YearsOverviewItem])
def get_years_overview(
    db: Session = Depends(get_database_session),
):
    """Return a years-overview for every logical meter.

    A logical meter is the newest meter in a replacement chain (or a standalone
    meter). Its consumption/cost history includes all predecessor meters'
    readings.
    """
    as_of_date = datetime.now(UTC).date()

    # Identify all "logical meters": meters that are NOT referenced by any
    # other meter's replaces_meter_id (i.e. they are the last in their chain).
    referenced_ids = (
        db.query(models.Meter.replaces_meter_id)
        .filter(models.Meter.replaces_meter_id.isnot(None))
        .distinct()
        .subquery()
    )
    logical_meters = (
        db.query(models.Meter)
        .outerjoin(referenced_ids, models.Meter.id == referenced_ids.c.replaces_meter_id)
        .filter(referenced_ids.c.replaces_meter_id.is_(None))
        .order_by(models.Meter.id.asc())
        .all()
    )

    results: list[schemas.YearsOverviewItem] = []
    for meter in logical_meters:
        chain = get_meter_chain(db, meter.id)
        years = _get_all_reading_years_for_chain(db, chain)

        year_entries: list[schemas.YearEntry] = []
        for year in years:
            consumption, cost, cost_basis, _message = _compute_yearly_cost_for_chain(
                db, meter.id, year, as_of_date, chain,
            )
            year_entries.append(schemas.YearEntry(
                year=year,
                consumption=str(consumption) if consumption is not None else None,
                cost=str(cost) if cost is not None else None,
                cost_basis=cost_basis,
            ))

        results.append(schemas.YearsOverviewItem(
            meter_id=meter.id,
            meter_label=meter.label,
            meter_type=meter.meter_type.value,
            unit=meter.unit,
            years=year_entries,
        ))

    return results
