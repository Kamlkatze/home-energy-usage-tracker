"""Meter replacement-chain consumption and cost logic."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from .cost_calculation import _CENT, _compute_cost_fields_multiperiod_raw
from .cost_queries import _get_overlapping_tariffs, _raise_if_negative

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
