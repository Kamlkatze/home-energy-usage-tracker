"""Costs API endpoints; calculation helpers live in app/services/."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..models.advance_payment import AdvancePaymentCategory
from ..services.cost_calculation import (
    _CENT,
    _GAS_CONVERSION_FIELDS_MESSAGE,
    _accumulate_costs,
    _combine_messages,
    _compute_cost_fields_multiperiod,
    _compute_cost_fields_multiperiod_breakdown,
    _compute_cost_fields_multiperiod_raw,
    _prorate_monthly,
    round_billed_consumption,
)
from ..services.cost_queries import (
    _get_active_tariff_for_date,
    _get_boundary_readings,
    _get_boundary_readings_for_wastewater,
    _get_boundary_readings_for_yearly_cost,
    _get_overlapping_tariffs,
    _raise_if_from_after_to,
    _raise_if_negative,
)
from ..services.meter_chain import get_meter_chain
from ..services.meter_chain_costs import (
    _accumulate_chain_costs_raw,
    _compute_chain_cost,
    _get_chain_consumption,
    _rescale_segments,
)
from ..services.projection import ProjectionService
from .deps import get_database_session

router = APIRouter()


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
        raw_consumption = end_reading.value - start_reading.value
        _raise_if_negative(raw_consumption)
        consumption = round_billed_consumption(raw_consumption)

        tariffs = _get_overlapping_tariffs(
            db, meter_id, models.TariffKind.CONSUMPTION, from_, to,
        )
        base_fee_total, total_cost, price_per_unit = _compute_cost_fields_multiperiod(
            consumption, tariffs, from_, to, meter_type=meter.meter_type,
        )
    else:
        # Chain path: follow the replacement chain.
        raw_consumption, segments = _get_chain_consumption(db, chain, from_, to)
        consumption = round_billed_consumption(raw_consumption)
        # Rescale the per-segment consumptions so they sum exactly to the
        # rounded (billed) total, keeping the proportional split.
        segments = _rescale_segments(segments, raw_consumption, consumption)
        base_fee_total, total_cost, price_per_unit = _compute_chain_cost(
            db, chain, segments, models.TariffKind.CONSUMPTION,
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

    # Cold water consumption — chain-aware
    cold_chain = get_meter_chain(db, water_cold_meter_id)
    cold_meter = cold_chain[-1]

    if len(cold_chain) == 1:
        start_reading, end_reading = _get_boundary_readings(
            db, water_cold_meter_id, from_, to,
        )
        cold_consumption = round_billed_consumption(
            end_reading.value - start_reading.value
        )
        _raise_if_negative(end_reading.value - start_reading.value)
    else:
        cold_consumption, _cold_segments = _get_chain_consumption(
            db, cold_chain, from_, to,
        )
        cold_consumption = round_billed_consumption(cold_consumption)

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
            garden_consumption = round_billed_consumption(
                garden_end.value - garden_start.value
            )
        else:
            garden_consumption, _ = _get_chain_consumption(
                db, garden_chain, from_, to,
            )
            garden_consumption = round_billed_consumption(garden_consumption)
        # A garden consumption exceeding the cold consumption is a data
        # quality issue that is not validated here; the wastewater
        # consumption is simply floored at 0.
    # Both billed quantities are whole m³ (see round_billed_consumption),
    # so the derived wastewater quantity is whole as well.
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
       (for completed years the period is clamped to Dec 31 of the viewed year)
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

        # For completed years, clamp the end of the cost period to Dec 31 of
        # the viewed year so that later readings (e.g. from a later year)
        # cannot inflate the consumption and fees.
        effective_end = min(as_of_date, date(year, 12, 31))

        # Use existing cost calculation logic for actual cost
        if as_of_date > year_start:
            # For ongoing years, use projection-like boundary reading logic
            # This ensures consistency with projection's actual_consumption_to_date
            boundary_readings = _get_boundary_readings_for_yearly_cost(
                db, meter_id, year, as_of_date, end_bound=effective_end,
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
                    # Calculate overlap with Jan 1 to effective_end period
                    cost_start_date = max(year_start, reading_start_date)
                    cost_end_date = min(effective_end, reading_end_date)

                    # Prorate consumption based on overlap days
                    overlap_days = (cost_end_date - cost_start_date).days
                    if overlap_days > 0:
                        prorated_consumption = (
                            total_consumption * Decimal(overlap_days) / Decimal(total_days)
                        )
                        # Billed quantity: whole units (projections stay
                        # unrounded, but the actual-cost path mirrors the
                        # invoice calculation).
                        prorated_consumption = round_billed_consumption(
                            prorated_consumption
                        )

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


@router.get(
    "/consumption-timeseries",
    response_model=list[schemas.ConsumptionTimeseriesItem],
)
def get_consumption_timeseries(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    meter_type: models.MeterType | None = Query(default=None),
    db: Session = Depends(get_database_session),
):
    """Return a time series of actual readings for every logical meter.

    Each reading is enriched with consumption and cost since the
    chronologically previous reading (which may lie outside the requested
    range or in a predecessor meter of the replacement chain).

    When ``meter_type`` is given, only logical meters of that type are
    returned; otherwise all types are returned (previous behaviour).
    """
    _raise_if_from_after_to(from_, to)

    # Identify logical meters (same logic as years-overview).
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

    if meter_type is not None:
        logical_meters = [
            meter for meter in logical_meters if meter.meter_type == meter_type
        ]

    results: list[schemas.ConsumptionTimeseriesItem] = []
    for meter in logical_meters:
        chain = get_meter_chain(db, meter.id)
        chain_ids = [m.id for m in chain]

        # All readings in [from_, to] from any meter in the chain, chronological.
        readings = (
            db.query(models.Reading)
            .filter(
                models.Reading.meter_id.in_(chain_ids),
                models.Reading.reading_date >= from_,
                models.Reading.reading_date <= to,
            )
            .order_by(models.Reading.reading_date.asc())
            .all()
        )

        if not readings:
            continue  # Omit logical meters with zero readings in range.

        points: list[schemas.ConsumptionTimeseriesPoint] = []
        prev_reading: models.Reading | None = None

        for idx, reading in enumerate(readings):
            if idx == 0:
                # Find chronologically previous reading anywhere in the chain.
                prev_reading = (
                    db.query(models.Reading)
                    .filter(
                        models.Reading.meter_id.in_(chain_ids),
                        models.Reading.reading_date < reading.reading_date,
                    )
                    .order_by(models.Reading.reading_date.desc())
                    .first()
                )

            consumption_str: str | None = None
            cost_str: str | None = None
            base_fee_str: str | None = None
            metering_fee_str: str | None = None
            energy_cost_str: str | None = None

            if prev_reading is not None:
                consumption_delta = reading.value - prev_reading.value
                if consumption_delta < 0:
                    # Negative consumption (e.g. counter reset at chain
                    # boundary); leave fields null for this point.
                    consumption_str = None
                    cost_str = None
                else:
                    # Billed quantity per reading interval: whole units
                    # (see round_billed_consumption).
                    consumption = round_billed_consumption(consumption_delta)
                    consumption_str = str(consumption)
                    try:
                        if meter.meter_type in (
                            models.MeterType.ELECTRICITY_EXPORT,
                            models.MeterType.ELECTRICITY_PRODUCTION,
                        ):
                            # Feed-in / generation meters carry a monetary value as
                            # an Einspeisevergütung (Vergütung), not a consumption
                            # cost. Compute it from the FEED_IN tariff (kWh × rate,
                            # no base fee) and report it as the per-point value.
                            tariffs = _get_overlapping_tariffs(
                                db,
                                reading.meter_id,
                                models.TariffKind.FEED_IN,
                                prev_reading.reading_date,
                                reading.reading_date,
                            )
                            _, _, verguetung_raw = _compute_cost_fields_multiperiod_raw(
                                consumption,
                                tariffs,
                                prev_reading.reading_date,
                                reading.reading_date,
                            )
                            verguetung = verguetung_raw.quantize(
                                _CENT, rounding=ROUND_HALF_UP
                            )
                            cost_str = str(verguetung)
                            base_fee_str = None
                            metering_fee_str = "0.00"
                            energy_cost_str = str(verguetung)
                        else:
                            tariffs = _get_overlapping_tariffs(
                                db,
                                reading.meter_id,
                                models.TariffKind.CONSUMPTION,
                                prev_reading.reading_date,
                                reading.reading_date,
                            )
                            base_fee, metering_fee, energy_cost = (
                                _compute_cost_fields_multiperiod_breakdown(
                                    consumption,
                                    tariffs,
                                    prev_reading.reading_date,
                                    reading.reading_date,
                                    meter_type=meter.meter_type,
                                )
                            )
                            total_cost = (
                                base_fee + metering_fee + energy_cost
                            ).quantize(_CENT, rounding=ROUND_HALF_UP)
                            cost_str = str(total_cost)
                            base_fee_str = str(base_fee)
                            metering_fee_str = str(metering_fee)
                            energy_cost_str = str(energy_cost)
                    except HTTPException:
                        # No tariff for this sub-period → value is null.
                        cost_str = None
                        base_fee_str = None
                        metering_fee_str = None
                        energy_cost_str = None

            points.append(schemas.ConsumptionTimeseriesPoint(
                date=reading.reading_date,
                value=str(reading.value),
                consumption_since_previous=consumption_str,
                cost_since_previous=cost_str,
                base_fee_since_previous=base_fee_str,
                metering_fee_since_previous=metering_fee_str,
                energy_cost_since_previous=energy_cost_str,
            ))

            prev_reading = reading

        results.append(schemas.ConsumptionTimeseriesItem(
            meter_id=meter.id,
            meter_label=meter.label,
            meter_type=meter.meter_type.value,
            unit=meter.unit,
            points=points,
        ))

    return results


# ---------------------------------------------------------------------------
# Category summary (per-category totals for an arbitrary date range)
# ---------------------------------------------------------------------------


@dataclass
class _ChainData:
    """Consumption, boundary readings, cost window and cost segments of one
    logical meter chain."""

    chain: list[models.Meter]
    consumption: Decimal
    segments: list[tuple[models.Meter, date, date, Decimal]] | None
    unit: str
    start_date: date
    start_value: Decimal
    end_date: date
    end_value: Decimal
    cost_start: date
    cost_end: date


def _logical_meters_of_type(
    db: Session, meter_type: models.MeterType,
) -> list[models.Meter]:
    """Return the logical meters (chain roots) of one meter type.

    Same chain-root logic as the consumption timeseries: a meter is a
    logical meter when no other meter references it via replaces_meter_id.
    """
    referenced_ids = (
        db.query(models.Meter.replaces_meter_id)
        .filter(models.Meter.replaces_meter_id.isnot(None))
        .distinct()
        .subquery()
    )
    return (
        db.query(models.Meter)
        .outerjoin(referenced_ids, models.Meter.id == referenced_ids.c.replaces_meter_id)
        .filter(
            referenced_ids.c.replaces_meter_id.is_(None),
            models.Meter.meter_type == meter_type,
        )
        .order_by(models.Meter.id.asc())
        .all()
    )


def _resolve_chain_consumption(
    db: Session,
    chain: list[models.Meter],
    from_: date,
    to: date,
) -> tuple[Decimal, models.Reading, models.Reading, list[tuple[models.Meter, date, date, Decimal]] | None] | None:
    """Resolve boundary readings and consumption for a chain over
    [from_, to] using the billing-period (Stichtag) convention.

    Start: the last reading on or before ``from_`` (the Abrechnungsstichtag
    that closes the previous period); fallback to the first reading on or
    after ``from_`` for meters installed mid-period. End: the last reading
    on or before ``to``. Consumption is the full delta between both
    readings; callers derive the cost window as
    [max(from_, start), min(to, end)].

    Returns None when no measurable consumption exists in the period.
    Raises HTTPException on negative consumption. For chains, the returned
    cost segments are already clamped to the cost window.
    """
    chain_ids = [m.id for m in chain]
    start_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id.in_(chain_ids),
            models.Reading.reading_date <= from_,
        )
        .order_by(models.Reading.reading_date.desc())
        .first()
    )
    if start_reading is None:
        # No reading before the period start (meter installed mid-period):
        # fall back to the first reading within the period.
        start_reading = (
            db.query(models.Reading)
            .filter(
                models.Reading.meter_id.in_(chain_ids),
                models.Reading.reading_date >= from_,
            )
            .order_by(models.Reading.reading_date.asc())
            .first()
        )
    end_reading = (
        db.query(models.Reading)
        .filter(
            models.Reading.meter_id.in_(chain_ids),
            models.Reading.reading_date <= to,
        )
        .order_by(models.Reading.reading_date.desc())
        .first()
    )
    if (
        start_reading is None
        or end_reading is None
        or end_reading.reading_date <= start_reading.reading_date
    ):
        return None
    raw_consumption = end_reading.value - start_reading.value
    _raise_if_negative(raw_consumption)
    consumption = round_billed_consumption(raw_consumption)

    if len(chain) == 1:
        segments = None
    else:
        # Clamp the cost segments to the cost window start: consumption
        # before 'from_' belongs to the previous billing period's costs.
        cost_start = max(from_, start_reading.reading_date)
        _total, segments = _get_chain_consumption(
            db, chain, start_reading.reading_date, to,
        )
        # Rescale the per-segment consumptions so they sum exactly to the
        # rounded (billed) total, keeping the proportional split.
        segments = [
            (meter, max(seg_from, cost_start), seg_to, seg_consumption)
            for meter, seg_from, seg_to, seg_consumption in _rescale_segments(
                segments, _total, consumption,
            )
            if max(seg_from, cost_start) < seg_to
        ] or None
    return consumption, start_reading, end_reading, segments


def _collect_chain_data(
    db: Session,
    meter_type: models.MeterType,
    from_: date,
    to: date,
) -> tuple[list[_ChainData], list[str]]:
    """Compute consumption (+ cost segments) for every logical meter chain
    of a meter type over [from_, to] (Stichtag convention, see
    _resolve_chain_consumption).

    Chains without measurable consumption in the range are skipped silently
    (they contribute nothing to the category, same as the timeseries). Data
    errors (negative consumption) are collected as messages.
    """
    chain_data: list[_ChainData] = []
    messages: list[str] = []
    for root in _logical_meters_of_type(db, meter_type):
        chain = get_meter_chain(db, root.id)
        try:
            resolved = _resolve_chain_consumption(db, chain, from_, to)
        except HTTPException as exc:
            detail = str(exc.detail)
            if "Zählerstand" in detail:
                # No readings in the range — skip silently.
                continue
            messages.append(detail)
            continue
        if resolved is None:
            continue
        consumption, start_reading, end_reading, segments = resolved
        chain_data.append(_ChainData(
            chain=chain, consumption=consumption, segments=segments, unit=chain[-1].unit,
            start_date=start_reading.reading_date, start_value=start_reading.value,
            end_date=end_reading.reading_date, end_value=end_reading.value,
            cost_start=max(from_, start_reading.reading_date),
            cost_end=min(to, end_reading.reading_date),
        ))
    return chain_data, messages


def _accumulate_category_costs(
    db: Session,
    chain_data: list[_ChainData],
    consumptions: list[Decimal],
    tariff_kind: models.TariffKind,
) -> tuple[Decimal, Decimal, Decimal]:
    """Accumulate unrounded (base, metering, energy) cost raw values across
    all chains of a category. Single meters are costed over their own cost
    window [cost_start, cost_end], chains use their (already clamped)
    per-meter segments. Raises HTTPException on the first chain whose
    tariffs cannot be resolved (mirrors the per-meter endpoints).
    """
    base_raw = metering_raw = energy_raw = Decimal(0)
    for cd, consumption in zip(chain_data, consumptions, strict=True):
        if cd.segments is None:
            tariffs = _get_overlapping_tariffs(
                db, cd.chain[0].id, tariff_kind, cd.cost_start, cd.cost_end,
            )
            b, m, e = _accumulate_costs(
                consumption, tariffs, cd.cost_start, cd.cost_end,
                meter_type=cd.chain[0].meter_type,
            )
        else:
            b, m, e = _accumulate_chain_costs_raw(db, cd.chain, cd.segments, tariff_kind)
        base_raw += b
        metering_raw += m
        energy_raw += e
    return base_raw, metering_raw, energy_raw


def _round_cost_parts(
    base_raw: Decimal, metering_raw: Decimal, energy_raw: Decimal,
) -> tuple[str, str, str, str]:
    """Round the three cost components at the output boundary and derive the
    total as the exact sum of the rounded parts (same convention as the
    consumption-timeseries breakdown, so displayed values add up)."""
    base = base_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    metering = metering_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    energy = energy_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    total = (base + metering + energy).quantize(_CENT, rounding=ROUND_HALF_UP)
    return str(base), str(metering), str(energy), str(total)


def _build_reading(
    cd: _ChainData,
    consumption: Decimal,
    garden: "_GardenChainData | None" = None,
    garden_share: Decimal | None = None,
) -> schemas.CategorySummaryReading:
    """Build one readings entry (boundary readings the consumption was
    derived from); garden info is attached when a single garden chain was
    used for the subtraction."""
    entry = schemas.CategorySummaryReading(
        meter_id=cd.chain[-1].id,
        meter_label=cd.chain[-1].label,
        start_date=cd.start_date,
        start_value=str(cd.start_value),
        end_date=cd.end_date,
        end_value=str(cd.end_value),
        consumption=str(consumption),
    )
    if garden is not None:
        entry.garden_meter_label = garden.meter.label
        entry.garden_start_date = garden.start_date
        entry.garden_start_value = str(garden.start_value)
        entry.garden_end_date = garden.end_date
        entry.garden_end_value = str(garden.end_value)
        if garden_share is not None:
            entry.garden_consumption = str(garden_share)
    return entry


def _build_category(
    consumption_total: Decimal | None,
    unit: str | None,
    cost_parts: tuple[str, str, str, str] | None,
    messages: list[str],
    readings: list[schemas.CategorySummaryReading] | None = None,
) -> schemas.CategorySummaryCategory:
    return schemas.CategorySummaryCategory(
        consumption=None if consumption_total is None else str(consumption_total),
        unit=unit,
        energy_cost=cost_parts[2] if cost_parts else None,
        base_fee_total=cost_parts[0] if cost_parts else None,
        metering_fee_total=cost_parts[1] if cost_parts else None,
        total_cost=cost_parts[3] if cost_parts else None,
        message=_combine_messages(*messages) or None,
        readings=readings or [],
    )


def _summarize_meter_type(
    db: Session,
    meter_type: models.MeterType,
    from_: date,
    to: date,
) -> schemas.CategorySummaryCategory | None:
    """Aggregate consumption + cost over all logical chains of a meter type.

    Returns None when no chain has readings in the range. Consumption stays
    available even when a cost component cannot be computed (missing tariff,
    gas conversion factors) — the cost fields become null and the reason is
    reported via message.
    """
    chain_data, messages = _collect_chain_data(db, meter_type, from_, to)
    if not chain_data:
        return None
    consumption_total = sum((cd.consumption for cd in chain_data), Decimal(0))
    cost_parts = None
    try:
        base_raw, metering_raw, energy_raw = _accumulate_category_costs(
            db, chain_data, [cd.consumption for cd in chain_data],
            models.TariffKind.CONSUMPTION,
        )
        cost_parts = _round_cost_parts(base_raw, metering_raw, energy_raw)
    except HTTPException as exc:
        messages.append(str(exc.detail))
    return _build_category(
        consumption_total, chain_data[0].unit, cost_parts, messages,
        readings=[_build_reading(cd, cd.consumption) for cd in chain_data],
    )


def _summarize_water(
    db: Session,
    from_: date,
    to: date,
) -> tuple[schemas.CategorySummaryCategory | None, list[_ChainData], Decimal]:
    """Aggregate cold-water consumption + cost; also returns the cold chain
    data and the total cold consumption for the wastewater derivation."""
    chain_data, messages = _collect_chain_data(db, models.MeterType.WATER_COLD, from_, to)
    if not chain_data:
        return None, [], Decimal(0)
    consumption_total = sum((cd.consumption for cd in chain_data), Decimal(0))
    cost_parts = None
    try:
        base_raw, metering_raw, energy_raw = _accumulate_category_costs(
            db, chain_data, [cd.consumption for cd in chain_data],
            models.TariffKind.CONSUMPTION,
        )
        cost_parts = _round_cost_parts(base_raw, metering_raw, energy_raw)
    except HTTPException as exc:
        messages.append(str(exc.detail))
    return (
        _build_category(
            consumption_total, chain_data[0].unit, cost_parts, messages,
            readings=[_build_reading(cd, cd.consumption) for cd in chain_data],
        ),
        chain_data,
        consumption_total,
    )


_GARDEN_NO_READINGS_MESSAGE = (
    "Gartenwasserzähler ohne Ablesungen im angegebenen Zeitraum – "
    "die Abwassermenge entspricht dem vollen Kaltwasserverbrauch."
)


@dataclass
class _GardenChainData:
    """Consumption and boundary readings of one garden-water chain."""

    meter: models.Meter
    consumption: Decimal
    start_date: date
    start_value: Decimal
    end_date: date
    end_value: Decimal


def _collect_garden_consumption(
    db: Session,
    from_: date,
    to: date,
) -> tuple[Decimal, list[_GardenChainData], list[str], bool]:
    """Sum the consumption of all garden-water chains over [from_, to]
    (Stichtag convention, see _resolve_chain_consumption).

    Garden meters carry no own tariff; only their consumption matters (it
    reduces the wastewater quantity). Chains without measurable consumption
    contribute 0; when garden meters exist but none has readings,
    has_data=False lets the caller add a hint message (wastewater then
    equals the full cold-water consumption).
    """
    logical = _logical_meters_of_type(db, models.MeterType.WATER_GARDEN)
    if not logical:
        return Decimal(0), [], [], True
    total = Decimal(0)
    entries: list[_GardenChainData] = []
    messages: list[str] = []
    has_data = False
    for root in logical:
        chain = get_meter_chain(db, root.id)
        try:
            resolved = _resolve_chain_consumption(db, chain, from_, to)
        except HTTPException as exc:
            detail = str(exc.detail)
            if "Zählerstand" in detail:
                continue
            messages.append(detail)
            continue
        if resolved is None:
            continue
        consumption, start_reading, end_reading, _segments = resolved
        has_data = True
        total += consumption
        entries.append(_GardenChainData(
            meter=chain[-1], consumption=consumption,
            start_date=start_reading.reading_date, start_value=start_reading.value,
            end_date=end_reading.reading_date, end_value=end_reading.value,
        ))
    return total, entries, messages, has_data


def _summarize_wastewater(
    db: Session,
    cold_chain_data: list[_ChainData],
    cold_total: Decimal,
    from_: date,
    to: date,
) -> schemas.CategorySummaryCategory | None:
    """Derive the wastewater category from the cold-water chain data.

    wastewater_consumption = max(0, cold_total - garden_total); with
    multiple cold chains the garden consumption is allocated proportionally
    to each chain's cold consumption. The wastewater tariff is attached to
    the cold-water meters (same rule as the wastewater endpoint).
    """
    if not cold_chain_data:
        return None
    garden_total, garden_entries, garden_messages, garden_has_data = (
        _collect_garden_consumption(db, from_, to)
    )
    messages = list(garden_messages)
    if not garden_has_data:
        messages.append(_GARDEN_NO_READINGS_MESSAGE)

    # Distribute the garden consumption proportionally across the cold
    # chains (exact 1:1 for the common single-chain case). Each chain's
    # billed wastewater quantity is a whole m³ (see round_billed_consumption).
    consumptions: list[Decimal] = []
    garden_shares: list[Decimal] = []
    for cd in cold_chain_data:
        if cold_total > 0:
            garden_share = garden_total * cd.consumption / cold_total
        else:
            garden_share = Decimal(0)
        garden_shares.append(garden_share)
        consumptions.append(round_billed_consumption(
            max(Decimal(0), cd.consumption - garden_share)
        ))
    wastewater_total = sum(consumptions, Decimal(0))

    readings = [
        # With exactly one garden chain the readings are unambiguous and
        # attached to every cold chain entry (its proportional share is
        # reported as garden_consumption).
        _build_reading(
            cd, consumption,
            garden=garden_entries[0] if len(garden_entries) == 1 else None,
            garden_share=garden_share if len(garden_entries) == 1 else None,
        )
        for cd, consumption, garden_share in zip(
            cold_chain_data, consumptions, garden_shares, strict=True,
        )
    ]

    cost_parts = None
    try:
        base_raw, metering_raw, energy_raw = _accumulate_category_costs(
            db, cold_chain_data, consumptions,
            models.TariffKind.WASTEWATER,
        )
        cost_parts = _round_cost_parts(base_raw, metering_raw, energy_raw)
    except HTTPException as exc:
        messages.append(str(exc.detail))
    return _build_category(
        wastewater_total, cold_chain_data[0].unit, cost_parts, messages,
        readings=readings,
    )


@router.get("/category-summary", response_model=schemas.CategorySummaryResponse)
def get_category_summary(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_database_session),
):
    """Aggregate consumption and cost per category (electricity, water,
    wastewater, gas) over an arbitrary date range.

    Billing-period (Stichtag) convention: consumption is the full delta
    from the last reading on/before 'from' to the last reading on/before
    'to' (matching how annual utility invoices are cut); the base/metering
    fees accrue from 'from' to the end of the cost window. Costs use the
    calendar-accurate multi-period tariff logic. Advance payments and the
    EEG feed-in compensation are intentionally NOT included here (separate
    providers / separate endpoint).
    """
    _raise_if_from_after_to(from_, to)
    water, cold_chain_data, cold_total = _summarize_water(db, from_, to)
    return schemas.CategorySummaryResponse(
        from_date=from_,
        to_date=to,
        electricity=_summarize_meter_type(
            db, models.MeterType.ELECTRICITY_IMPORT, from_, to,
        ),
        water=water,
        wastewater=_summarize_wastewater(
            db, cold_chain_data, cold_total, from_, to,
        ),
        gas=_summarize_meter_type(db, models.MeterType.GAS, from_, to),
    )
