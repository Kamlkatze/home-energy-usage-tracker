"""Cost calculation building blocks: pure math, no DB access.

Money is rounded once, at the response boundary (never on intermediate
values, per AGENTS.md).
"""

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

from .. import models

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


def _compute_cost_fields(
    consumption: Decimal, tariff: models.TariffPeriod, from_: date, to: date,
) -> tuple[Decimal, Decimal]:
    """Compute (base_fee_total, total_cost) for a single tariff period.

    Base fee and metering fee are prorated by calendar-accurate month
    lengths; money is rounded once at the output boundary (AGENTS.md).
    """
    # A null fee is treated as 0.
    base_fee_monthly = (
        tariff.base_fee_monthly if tariff.base_fee_monthly is not None else Decimal(0)
    )
    metering_fee_monthly = (
        tariff.metering_fee_monthly
        if tariff.metering_fee_monthly is not None
        else Decimal(0)
    )
    base_fee_total_raw = _prorate_monthly(base_fee_monthly, from_, to)
    metering_fee_total_raw = _prorate_monthly(metering_fee_monthly, from_, to)

    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    fixed_cost_raw = base_fee_total_raw + metering_fee_total_raw
    total_cost = (consumption * tariff.price_per_unit + fixed_cost_raw).quantize(
        _CENT, rounding=ROUND_HALF_UP,
    )
    return base_fee_total, total_cost


def _accumulate_costs(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Accumulate unrounded (base_fee_raw, metering_fee_raw, energy_cost_raw) across
    overlapping tariff periods over the inclusive-exclusive range [from_, to).

    Consumption is allocated proportionally by overlapping days in each period.
    Base and metering fees are prorated by calendar-accurate month lengths;
    nothing is rounded here (round at the output boundary, per AGENTS.md).

    For gas meters (meter_type=MeterType.GAS) the per-period consumption
    share (m³) is converted to kWh with that period's own conversion
    factors BEFORE applying price_per_unit:
        kWh = m³ * gas_z_zahl (Zustandszahl) * gas_brennwert (kWh/m³)
    Both fields are required on every overlapping gas tariff period; a
    missing value raises a 422. Non-gas meters pass meter_type=None and
    are completely unaffected.

    Tariff periods [valid_from, valid_to] are inclusive on both ends (DB
    daterange '[]').
    """
    total_days = Decimal((to - from_).days)
    if total_days == 0:
        # Defensive: _raise_if_from_after_to normally prevents this.
        total_days = Decimal("0.000001")

    base_fee_total_raw = Decimal(0)
    metering_fee_total_raw = Decimal(0)
    energy_cost_raw = Decimal(0)

    for tariff in tariffs:
        period_start = max(from_, tariff.valid_from)
        period_end = to
        if tariff.valid_to is not None:
            period_end = min(to, tariff.valid_to + timedelta(days=1))  # valid_to inclusive

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
        metering_fee_monthly = (
            tariff.metering_fee_monthly
            if tariff.metering_fee_monthly is not None
            else Decimal(0)
        )
        base_fee_total_raw += _prorate_monthly(base_fee_monthly, period_start, period_end)
        metering_fee_total_raw += _prorate_monthly(
            metering_fee_monthly, period_start, period_end
        )
        energy_cost_raw += consumption_in_period * tariff.price_per_unit

    return base_fee_total_raw, metering_fee_total_raw, energy_cost_raw


def _compute_cost_fields_multiperiod(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (base_fee_total, total_cost, first_price_per_unit) for multiple periods.

    Consumption is allocated proportionally by overlapping days in each period.
    Base and metering fees are prorated by calendar-accurate month lengths;
    money is rounded once at the output boundary (AGENTS.md).

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
    base_fee_total_raw, metering_fee_total_raw, energy_cost_raw = _accumulate_costs(
        consumption, tariffs, from_, to, meter_type=meter_type
    )

    # Round only at the output boundary (AGENTS.md).
    base_fee_total = base_fee_total_raw.quantize(_CENT, rounding=ROUND_HALF_UP)
    fixed_cost_raw = base_fee_total_raw + metering_fee_total_raw
    total_cost = (energy_cost_raw + fixed_cost_raw).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )

    # Return first period's price for backward compatibility
    first_price_per_unit = tariffs[0].price_per_unit

    return base_fee_total, total_cost, first_price_per_unit


def _compute_cost_fields_multiperiod_raw(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Like _compute_cost_fields_multiperiod but returns
    (base_fee_raw, metering_fee_raw, energy_cost_raw) without rounding,
    for accumulation across chain segments.
    """
    return _accumulate_costs(consumption, tariffs, from_, to, meter_type=meter_type)


def _compute_cost_fields_multiperiod_breakdown(
    consumption: Decimal,
    tariffs: list[models.TariffPeriod],
    from_: date,
    to: date,
    meter_type: models.MeterType | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute the rounded (base_fee_total, metering_fee_total, energy_cost_total)
    breakdown for a single interval, for per-point cost breakdowns in API responses.

    The returned energy cost is the pure variable cost (price_per_unit ×
    converted/allocated consumption); base and metering fees are prorated
    calendar-accurately. Money is rounded once at the output boundary (AGENTS.md).
    """
    base_fee_raw, metering_fee_raw, energy_cost_raw = _accumulate_costs(
        consumption, tariffs, from_, to, meter_type=meter_type
    )
    return (
        base_fee_raw.quantize(_CENT, rounding=ROUND_HALF_UP),
        metering_fee_raw.quantize(_CENT, rounding=ROUND_HALF_UP),
        energy_cost_raw.quantize(_CENT, rounding=ROUND_HALF_UP),
    )
