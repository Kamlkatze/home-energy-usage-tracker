from datetime import UTC, date, datetime
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

# Fixed EEG 2009 threshold: 30% of production is the self-consumption
# limit for tier-1 pricing. Not configurable — this is a statutory value
# from EEG 2009 § 33 Abs. 2.
_EEG_2009_THRESHOLD = Decimal("0.3")


def _get_meter_or_404(db: Session, meter_id: int) -> models.Meter:
    meter = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if meter is None:
        raise HTTPException(status_code=404, detail="Zähler nicht gefunden.")
    return meter


def _get_boundary_readings(
    db: Session, meter_id: int, from_: date, to: date
) -> tuple[models.Reading, models.Reading]:
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
        raise HTTPException(
            status_code=422,
            detail=(
                "Der ermittelte Verbrauch ist negativ "
                "(möglicher Zählerüberlauf). Bitte Zählerstände prüfen."
            ),
        )


def _raise_if_from_after_to(from_: date, to: date) -> None:
    if from_ > to:
        raise HTTPException(
            status_code=422,
            detail="Ungültiger Zeitraum: 'from' muss kleiner oder gleich 'to' sein.",
        )


def _get_feed_in_eeg2009_tariff(
    db: Session, meter_id: int, from_: date, to: date
) -> models.TariffPeriod:
    """Find the active feed_in_eeg2009 tariff for the export meter.

    The EEG 2009 tariff is attached to the export meter (not the production
    meter), because the feed-in compensation historically relates to the
    electricity fed into the grid at the export metering point.
    """
    tariff = (
        db.query(models.TariffPeriod)
        .filter(
            models.TariffPeriod.meter_id == meter_id,
            models.TariffPeriod.tariff_kind == models.TariffKind.FEED_IN_EEG2009,
            models.TariffPeriod.valid_from <= to,
            or_(
                models.TariffPeriod.valid_to.is_(None),
                models.TariffPeriod.valid_to >= from_,
            ),
        )
        .order_by(models.TariffPeriod.valid_from.asc())
        .first()
    )
    if tariff is None:
        raise HTTPException(
            status_code=404,
            detail="Kein aktiver EEG 2009-Einspeisetarif für diesen Zeitraum gefunden.",
        )

    # Verify the range is fully covered (first tariff must start at or before from_)
    if tariff.valid_from > from_:
        raise HTTPException(
            status_code=404,
            detail="Kein aktiver EEG 2009-Einspeisetarif für diesen Zeitraum gefunden.",
        )
    if tariff.valid_to is not None and tariff.valid_to < to:
        raise HTTPException(
            status_code=404,
            detail="Kein aktiver EEG 2009-Einspeisetarif für diesen Zeitraum gefunden.",
        )

    return tariff


@router.get("/feed-in-compensation", response_model=schemas.FeedInCompensationResponse)
def calculate_feed_in_compensation(
    production_meter_id: int = Query(...),
    export_meter_id: int = Query(...),
    # import_meter_id is accepted for future extensibility (e.g. EEG
    # formulas that may require import data). Currently unused in the
    # EEG 2009 calculation — only P (production) and E (export) are
    # relevant. See Anforderungen.md.
    import_meter_id: int | None = Query(None),
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_database_session),
):
    _raise_if_from_after_to(from_, to)

    # Validate that the meters exist
    _get_meter_or_404(db, production_meter_id)
    _get_meter_or_404(db, export_meter_id)

    # Note: Meter-replacement-chain support is NOT implemented for this
    # endpoint (first iteration). This is a known limitation, similar to
    # other "no chain support" features in the project.

    # Production consumption (P)
    prod_start, prod_end = _get_boundary_readings(db, production_meter_id, from_, to)
    production_consumption = prod_end.value - prod_start.value
    _raise_if_negative(production_consumption)

    # Export consumption (E)
    exp_start, exp_end = _get_boundary_readings(db, export_meter_id, from_, to)
    export_consumption = exp_end.value - exp_start.value
    _raise_if_negative(export_consumption)

    # The EEG 2009 tariff is attached to the export meter (see
    # _get_feed_in_eeg2009_tariff docstring for rationale).
    tariff = _get_feed_in_eeg2009_tariff(db, export_meter_id, from_, to)

    # --- EEG 2009 § 33 Abs. 2 calculation ---
    # P = production_consumption (total generation)
    # E = export_consumption (electricity fed into grid)
    # S = P - E (self-consumption; floored at 0 — you cannot self-consume
    #     a negative amount, even if data somehow shows export > production).
    P = production_consumption
    E = export_consumption
    S = max(Decimal(0), P - E)

    # 30 % threshold on self-consumption
    # Fixed EEG 2009 threshold, not configurable
    threshold_kwh = P * _EEG_2009_THRESHOLD

    tier1_kwh = min(S, threshold_kwh)
    tier2_kwh = max(Decimal(0), S - threshold_kwh)

    days = Decimal((to - from_).days)

    # Rates from the tariff (treat None as 0)
    tier1_rate = tariff.eeg_tier1_rate if tariff.eeg_tier1_rate is not None else Decimal(0)
    tier2_rate = tariff.eeg_tier2_rate if tariff.eeg_tier2_rate is not None else Decimal(0)
    metering_point_fee = (
        tariff.metering_point_fee_yearly
        if tariff.metering_point_fee_yearly is not None
        else Decimal(0)
    )

    # Gross compensation (before the metering point fee deduction):
    #   P × price_per_unit (full production paid at feed-in rate)
    #   − tier1_kwh × eeg_tier1_rate (repayment for tier-1 self-consumption)
    #   − tier2_kwh × eeg_tier2_rate (repayment for tier-2 self-consumption)
    gross_compensation = (
        P * tariff.price_per_unit
        - tier1_kwh * tier1_rate
        - tier2_kwh * tier2_rate
    ).quantize(_CENT, rounding=ROUND_HALF_UP)

    # Metering point fee, prorated for the period (annual fee × days / 365).
    metering_point_fee_deducted = (
        days * metering_point_fee / Decimal(365)
    ).quantize(_CENT, rounding=ROUND_HALF_UP)

    # Total compensation:
    #   gross_compensation (before the fee deduction)
    #   − metering_point_fee_deducted (prorated annual fee)
    total_raw = (
        P * tariff.price_per_unit
        - tier1_kwh * tier1_rate
        - tier2_kwh * tier2_rate
        - days * metering_point_fee / Decimal(365)
    )

    total_compensation = total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)

    return schemas.FeedInCompensationResponse(
        production_meter_id=production_meter_id,
        export_meter_id=export_meter_id,
        from_date=from_,
        to_date=to,
        production_consumption=production_consumption,
        export_consumption=export_consumption,
        self_consumption=S,
        tier1_kwh=tier1_kwh,
        tier2_kwh=tier2_kwh,
        total_compensation=total_compensation,
        gross_compensation=gross_compensation,
        metering_point_fee_deducted=metering_point_fee_deducted,
    )


@router.get(
    "/feed-in-compensation-projection",
    response_model=schemas.FeedInCompensationProjectionResponse,
)
def calculate_feed_in_compensation_projection(
    production_meter_id: int = Query(...),
    export_meter_id: int = Query(...),
    year: int = Query(...),
    db: Session = Depends(get_database_session),
):
    _get_meter_or_404(db, production_meter_id)
    _get_meter_or_404(db, export_meter_id)

    as_of_date = datetime.now(UTC).date()

    # Get projected annual consumption for both meters
    try:
        prod_projection = ProjectionService.calculate_projection(
            db=db, meter_id=production_meter_id, year=year, as_of_date=as_of_date
        )
        exp_projection = ProjectionService.calculate_projection(
            db=db, meter_id=export_meter_id, year=year, as_of_date=as_of_date
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if prod_projection["basis"] == "insufficient_data" or (
        prod_projection["projected_annual_consumption"] is None
    ):
        return schemas.FeedInCompensationProjectionResponse(
            production_meter_id=production_meter_id,
            export_meter_id=export_meter_id,
            year=year,
            production_consumption=None,
            export_consumption=None,
            self_consumption=None,
            tier1_kwh=None,
            tier2_kwh=None,
            total_compensation=None,
            basis=prod_projection["basis"],
            message=prod_projection.get("message"),
        )

    P = prod_projection["projected_annual_consumption"]
    E = exp_projection["projected_annual_consumption"] if exp_projection["projected_annual_consumption"] is not None else Decimal(0)
    S = max(Decimal(0), P - E)

    threshold_kwh = P * _EEG_2009_THRESHOLD
    tier1_kwh = min(S, threshold_kwh)
    tier2_kwh = max(Decimal(0), S - threshold_kwh)

    # Look up EEG tariff on the export meter for the full year
    from_date = date(year, 1, 1)
    to_date = date(year, 12, 31)
    tariff = _get_feed_in_eeg2009_tariff(db, export_meter_id, from_date, to_date)

    tier1_rate = tariff.eeg_tier1_rate if tariff.eeg_tier1_rate is not None else Decimal(0)
    tier2_rate = tariff.eeg_tier2_rate if tariff.eeg_tier2_rate is not None else Decimal(0)
    metering_point_fee = (
        tariff.metering_point_fee_yearly
        if tariff.metering_point_fee_yearly is not None
        else Decimal(0)
    )

    days = Decimal((to_date - from_date).days)
    total_raw = (
        P * tariff.price_per_unit
        - tier1_kwh * tier1_rate
        - tier2_kwh * tier2_rate
        - days * metering_point_fee / Decimal(365)
    )
    total_compensation = total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)

    return schemas.FeedInCompensationProjectionResponse(
        production_meter_id=production_meter_id,
        export_meter_id=export_meter_id,
        year=year,
        production_consumption=P,
        export_consumption=E,
        self_consumption=S,
        tier1_kwh=tier1_kwh,
        tier2_kwh=tier2_kwh,
        total_compensation=total_compensation,
        basis=prod_projection["basis"],
        message=None,
    )