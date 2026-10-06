"""DB lookup and validation helpers shared by the costs endpoints."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models


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
    end_bound: date | None = None,
) -> tuple[models.Reading, models.Reading] | tuple[None, None]:
    """Find boundary readings for yearly cost calculation.

    Similar to projection logic:
    - Start: prefer reading on Dec 31 of previous year, fallback to first reading in year
    - End: last reading <= as_of_date (optionally clamped to end_bound, e.g.
      Dec 31 of the viewed year for completed years, so that readings after
      the viewed year do not inflate the consumption)
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

    # End reading: last reading <= as_of_date (clamped to end_bound if given)
    effective_end = as_of_date if end_bound is None else min(as_of_date, end_bound)
    end_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id == meter_id,
            models.Reading.reading_date <= effective_end,
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
