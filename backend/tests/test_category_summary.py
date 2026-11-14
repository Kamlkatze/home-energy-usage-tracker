"""
Tests for the category summary endpoint (GET /api/costs/category-summary).

Aggregates consumption and cost per category (electricity, water,
wastewater, gas) over an arbitrary date range, day-exact: consumption from
boundary readings clamped to the range, costs via the calendar-accurate
multi-period tariff logic. Wastewater is derived from the cold-water
chains (cold - garden) and billed against the wastewater tariff attached
to the cold-water meters.
"""
from decimal import Decimal


def _create_meter(client, meter_type, label="Test Meter", replaces_meter_id=None):
    payload = {"meter_type": meter_type, "label": label}
    if replaces_meter_id is not None:
        payload["replaces_meter_id"] = replaces_meter_id
    response = client.post("/api/meters/", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_reading(client, meter_id, value, reading_date):
    response = client.post(
        "/api/readings/",
        json={"meter_id": meter_id, "value": value, "reading_date": reading_date},
    )
    assert response.status_code == 200, response.text


def _create_tariff(
    client, meter_id, valid_from, valid_to, price_per_unit,
    base_fee_monthly=None, metering_fee_monthly=None,
    tariff_kind="consumption", gas_z_zahl=None, gas_brennwert=None,
):
    payload = {
        "meter_id": meter_id,
        "tariff_kind": tariff_kind,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "price_per_unit": price_per_unit,
    }
    if base_fee_monthly is not None:
        payload["base_fee_monthly"] = base_fee_monthly
    if metering_fee_monthly is not None:
        payload["metering_fee_monthly"] = metering_fee_monthly
    if gas_z_zahl is not None:
        payload["gas_z_zahl"] = gas_z_zahl
    if gas_brennwert is not None:
        payload["gas_brennwert"] = gas_brennwert
    response = client.post("/api/tariffs/", json=payload)
    assert response.status_code == 200, response.text


def _get_summary(client, from_, to):
    return client.get(
        "/api/costs/category-summary", params={"from": from_, "to": to},
    )


def test_category_summary_all_categories(client):
    """Exact arithmetic for all four categories with two electricity meters.

    Range 2024-01-10..2024-03-10: base fee factor = 62/31 = 2.0 months.

    Electricity 1: 1000.000 -> 1150.500 kWh (150.500 -> billed 151),
      price 0.30, base 10.00/mo, metering 2.00/mo:
      energy 45.30, base 20.00, metering 4.00, total 69.30
    Electricity 2: 100.000 -> 200.000 kWh (100.000), price 0.25,
      base 6.00/mo, metering 1.00/mo:
      energy 25.00, base 12.00, metering 2.00, total 39.00
    -> electricity: consumption 251, energy 70.30, base 32.00,
       metering 6.00, total 108.30
    Water (cold): 1000.000 -> 1150.500 m³ (150.500 -> billed 151),
      price 2.00000, no fees: total 302.00
    Garden: 20.000 -> 79.500 m³ (59.500 -> billed 60) -> wastewater 91,
      wastewater price 2.10000, base 6.00/mo:
      base 12.00, energy 191.10, total 203.10
    Gas: 500.000 -> 620.000 m³ (120.000), z=0.95, brennwert=10 -> 1140 kWh,
      price 0.10000, base 5.00/mo: energy 114.00, base 10.00, total 124.00
    """
    e1 = _create_meter(client, "electricity_import", "Strom 1")
    e2 = _create_meter(client, "electricity_import", "Strom 2")
    cold = _create_meter(client, "water_cold", "Kaltwasser")
    garden = _create_meter(client, "water_garden", "Garten")
    gas = _create_meter(client, "gas", "Gas")

    _create_reading(client, e1, "1000.000", "2024-01-10")
    _create_reading(client, e1, "1150.500", "2024-03-10")
    _create_reading(client, e2, "100.000", "2024-01-10")
    _create_reading(client, e2, "200.000", "2024-03-10")
    _create_reading(client, cold, "1000.000", "2024-01-10")
    _create_reading(client, cold, "1150.500", "2024-03-10")
    _create_reading(client, garden, "20.000", "2024-01-10")
    _create_reading(client, garden, "79.500", "2024-03-10")
    _create_reading(client, gas, "500.000", "2024-01-10")
    _create_reading(client, gas, "620.000", "2024-03-10")

    _create_tariff(client, e1, "2024-01-01", "2024-12-31", "0.30000",
                   base_fee_monthly="10.00", metering_fee_monthly="2.00")
    _create_tariff(client, e2, "2024-01-01", "2024-12-31", "0.25000",
                   base_fee_monthly="6.00", metering_fee_monthly="1.00")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.00000")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.10000",
                   base_fee_monthly="6.00", tariff_kind="wastewater")
    _create_tariff(client, gas, "2024-01-01", "2024-12-31", "0.10000",
                   base_fee_monthly="5.00", gas_z_zahl="0.95",
                   gas_brennwert="10.0")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["from_date"] == "2024-01-10"
    assert data["to_date"] == "2024-03-10"

    electricity = data["electricity"]
    assert electricity["unit"] == "kWh"
    assert Decimal(electricity["consumption"]) == Decimal(251)
    assert Decimal(electricity["energy_cost"]) == Decimal("70.30")
    assert Decimal(electricity["base_fee_total"]) == Decimal("32.00")
    assert Decimal(electricity["metering_fee_total"]) == Decimal("6.00")
    assert Decimal(electricity["total_cost"]) == Decimal("108.30")
    assert electricity["message"] is None

    water = data["water"]
    assert water["unit"] == "m³"
    assert Decimal(water["consumption"]) == Decimal(151)
    assert Decimal(water["energy_cost"]) == Decimal("302.00")
    assert Decimal(water["base_fee_total"]) == Decimal("0.00")
    assert Decimal(water["metering_fee_total"]) == Decimal("0.00")
    assert Decimal(water["total_cost"]) == Decimal("302.00")

    wastewater = data["wastewater"]
    assert wastewater["unit"] == "m³"
    assert Decimal(wastewater["consumption"]) == Decimal("91.000")
    assert Decimal(wastewater["base_fee_total"]) == Decimal("12.00")
    assert Decimal(wastewater["energy_cost"]) == Decimal("191.10")
    assert Decimal(wastewater["total_cost"]) == Decimal("203.10")

    gas_data = data["gas"]
    assert gas_data["unit"] == "m³"
    assert Decimal(gas_data["consumption"]) == Decimal("120.000")
    assert Decimal(gas_data["energy_cost"]) == Decimal("114.00")
    assert Decimal(gas_data["base_fee_total"]) == Decimal("10.00")
    assert Decimal(gas_data["total_cost"]) == Decimal("124.00")

    # Underlying boundary readings per contributing meter
    electricity_readings = data["electricity"]["readings"]
    assert len(electricity_readings) == 2
    by_meter = {r["meter_id"]: r for r in electricity_readings}
    assert by_meter[e1]["meter_label"] == "Strom 1"
    assert by_meter[e1]["start_date"] == "2024-01-10"
    assert Decimal(by_meter[e1]["start_value"]) == Decimal("1000.000")
    assert by_meter[e1]["end_date"] == "2024-03-10"
    assert Decimal(by_meter[e1]["end_value"]) == Decimal("1150.500")
    assert Decimal(by_meter[e1]["consumption"]) == Decimal(151)
    assert by_meter[e1]["garden_meter_label"] is None

    wastewater_readings = data["wastewater"]["readings"]
    assert len(wastewater_readings) == 1
    ww = wastewater_readings[0]
    assert ww["meter_id"] == cold
    assert Decimal(ww["consumption"]) == Decimal("91.000")
    assert ww["garden_meter_label"] == "Garten"
    assert ww["garden_start_date"] == "2024-01-10"
    assert Decimal(ww["garden_start_value"]) == Decimal("20.000")
    assert ww["garden_end_date"] == "2024-03-10"
    assert Decimal(ww["garden_end_value"]) == Decimal("79.500")
    assert Decimal(ww["garden_consumption"]) == Decimal(60)


def test_category_summary_partial_categories(client):
    """Categories without meters/readings in the range are null."""
    meter_id = _create_meter(client, "electricity_import", "Nur Strom")
    _create_reading(client, meter_id, "1000.000", "2024-01-01")
    _create_reading(client, meter_id, "1100.000", "2024-06-01")
    _create_tariff(client, meter_id, "2024-01-01", None, "0.30000",
                   base_fee_monthly="10.00")

    response = _get_summary(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()

    assert data["electricity"] is not None
    assert Decimal(data["electricity"]["consumption"]) == Decimal("100.000")
    assert data["water"] is None
    assert data["wastewater"] is None
    assert data["gas"] is None


def test_category_summary_no_meters(client):
    """Empty database: all categories null."""
    response = _get_summary(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()
    assert data["electricity"] is None
    assert data["water"] is None
    assert data["wastewater"] is None
    assert data["gas"] is None


def test_category_summary_wastewater_garden_exceeds_cold(client):
    """Garden consumption above cold consumption: wastewater floored at 0.

    Only the prorated wastewater base fee remains:
      base = 6.00 * 62/31 = 12.00, total 12.00
    """
    cold = _create_meter(client, "water_cold", "Kaltwasser")
    garden = _create_meter(client, "water_garden", "Garten")
    _create_reading(client, cold, "100.000", "2024-01-10")
    _create_reading(client, cold, "200.000", "2024-03-10")
    _create_reading(client, garden, "50.000", "2024-01-10")
    _create_reading(client, garden, "200.000", "2024-03-10")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.00000")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.10000",
                   base_fee_monthly="6.00", tariff_kind="wastewater")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["water"]["consumption"]) == Decimal("100.000")
    assert Decimal(data["wastewater"]["consumption"]) == Decimal("0.000")
    assert Decimal(data["wastewater"]["total_cost"]) == Decimal("12.00")
    assert data["wastewater"]["message"] is None


def test_category_summary_garden_meter_without_readings(client):
    """Garden meter exists but has no readings in the range: wastewater
    equals the full cold consumption and a hint message is returned."""
    cold = _create_meter(client, "water_cold", "Kaltwasser")
    garden = _create_meter(client, "water_garden", "Garten")
    _create_reading(client, cold, "1000.000", "2024-01-10")
    _create_reading(client, cold, "1150.500", "2024-03-10")
    _create_reading(client, garden, "20.000", "2025-01-10")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.00000")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.10000",
                   base_fee_monthly="6.00", tariff_kind="wastewater")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    wastewater = data["wastewater"]
    assert Decimal(wastewater["consumption"]) == Decimal(151)
    assert wastewater["message"] is not None
    assert "Gartenwasserzähler" in wastewater["message"]
    # The cold readings are still reported; no garden info (no garden data)
    assert len(wastewater["readings"]) == 1
    assert Decimal(wastewater["readings"][0]["consumption"]) == Decimal(151)
    assert wastewater["readings"][0]["garden_meter_label"] is None


def test_category_summary_no_wastewater_tariff(client):
    """Cold water works, wastewater tariff missing: wastewater cost null
    with message, cold-water consumption still reported."""
    cold = _create_meter(client, "water_cold", "Kaltwasser")
    _create_reading(client, cold, "1000.000", "2024-01-10")
    _create_reading(client, cold, "1150.500", "2024-03-10")
    _create_tariff(client, cold, "2024-01-01", "2024-12-31", "2.00000")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["water"]["total_cost"]) == Decimal("302.00")
    wastewater = data["wastewater"]
    assert wastewater is not None
    assert Decimal(wastewater["consumption"]) == Decimal(151)
    assert wastewater["total_cost"] is None
    assert wastewater["energy_cost"] is None
    assert "Kein gültiger Tarif" in wastewater["message"]


def test_category_summary_gas_missing_conversion_factors(client):
    """Gas tariff without z-zahl/brennwert: gas consumption present, cost
    null with explanatory message."""
    meter_id = _create_meter(client, "gas", "Gas")
    _create_reading(client, meter_id, "500.000", "2024-01-10")
    _create_reading(client, meter_id, "620.000", "2024-03-10")
    _create_tariff(client, meter_id, "2024-01-01", "2024-12-31", "0.10000",
                   base_fee_monthly="5.00")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    gas_data = data["gas"]
    assert Decimal(gas_data["consumption"]) == Decimal("120.000")
    assert gas_data["total_cost"] is None
    assert gas_data["message"] is not None
    assert "gas_z_zahl" in gas_data["message"]


def test_category_summary_missing_tariff(client):
    """Meter with readings but no tariff: consumption present, cost null
    with message."""
    meter_id = _create_meter(client, "electricity_import", "Ohne Tarif")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")

    response = _get_summary(client, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    electricity = data["electricity"]
    assert Decimal(electricity["consumption"]) == Decimal(151)
    assert electricity["total_cost"] is None
    assert "Kein gültiger Tarif" in electricity["message"]


def test_category_summary_replacement_chain(client):
    """Replacement chain: both meters' segments are aggregated.

    Old: 1000.000 @ 2024-01-01 -> 1500.000 @ 2024-06-30 (500.000),
      price 0.30, base 10.00/mo -> energy 150.00,
      base 5 full months + June prorated 29/30 = 59.67 raw
    New (replaces old, carry-over 1500): 1500.000 @ 2024-07-01 ->
      1700.000 @ 2024-12-31 (200.000), price 0.40, base 12.00/mo ->
      energy 80.00, base 5 full months + Dec prorated 30/31 = 71.61 raw
    -> consumption 700.000, energy 230.00, base 131.28, total 361.28
    (each segment's end reading date is exclusive, so the segment end day
    adds no base fee; raw values are summed across segments and rounded once)
    """
    old_id = _create_meter(client, "electricity_import", "Alt")
    new_id = _create_meter(client, "electricity_import", "Neu",
                           replaces_meter_id=old_id)
    _create_reading(client, old_id, "1000.000", "2024-01-01")
    _create_reading(client, old_id, "1500.000", "2024-06-30")
    _create_reading(client, new_id, "1500.000", "2024-07-01")
    _create_reading(client, new_id, "1700.000", "2024-12-31")
    _create_tariff(client, old_id, "2024-01-01", None, "0.30000",
                   base_fee_monthly="10.00")
    _create_tariff(client, new_id, "2024-01-01", None, "0.40000",
                   base_fee_monthly="12.00")

    response = _get_summary(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()

    electricity = data["electricity"]
    assert Decimal(electricity["consumption"]) == Decimal("700.000")
    assert Decimal(electricity["energy_cost"]) == Decimal("230.00")
    assert Decimal(electricity["base_fee_total"]) == Decimal("131.28")
    assert Decimal(electricity["metering_fee_total"]) == Decimal("0.00")
    assert Decimal(electricity["total_cost"]) == Decimal("361.28")

    # Boundary readings span the whole chain: first reading on the
    # predecessor, last reading on the successor.
    readings = electricity["readings"]
    assert len(readings) == 1
    assert readings[0]["meter_id"] == new_id
    assert readings[0]["start_date"] == "2024-01-01"
    assert Decimal(readings[0]["start_value"]) == Decimal("1000.000")
    assert readings[0]["end_date"] == "2024-12-31"
    assert Decimal(readings[0]["end_value"]) == Decimal("1700.000")


def test_category_summary_stichtag_start_before_range(client):
    """Billing-period convention: the start reading is the last reading on
    or before the requested start (Stichtag), even when it lies before the
    range.

    Readings 1000.000 @ 2025-10-21 and 1150.500 @ 2026-10-22, range
    2025-10-22..2026-10-22 (annual invoice period):
      consumption = 150.500 -> billed 151 (full delta from Stichtag reading)
      energy      = 151 * 0.30 = 45.30
      base fee    = 10.00/mo over 2025-10-22..2026-10-22 =
                    10 * (10/31 + 2 + 9 + 21/31) = 120.00 (12 full months)
      total       = 165.30
    """
    meter_id = _create_meter(client, "electricity_import", "Strom")
    _create_reading(client, meter_id, "1000.000", "2025-10-21")
    _create_reading(client, meter_id, "1150.500", "2026-10-22")
    _create_tariff(client, meter_id, "2025-01-01", None, "0.30000",
                   base_fee_monthly="10.00")

    response = _get_summary(client, "2025-10-22", "2026-10-22")
    assert response.status_code == 200
    data = response.json()

    electricity = data["electricity"]
    assert Decimal(electricity["consumption"]) == Decimal(151)
    assert Decimal(electricity["energy_cost"]) == Decimal("45.30")
    assert Decimal(electricity["base_fee_total"]) == Decimal("120.00")
    assert Decimal(electricity["total_cost"]) == Decimal("165.30")

    # The readings shown are the Stichtag pair (21.10.2025 -> 22.10.2026)
    readings = electricity["readings"]
    assert len(readings) == 1
    assert readings[0]["start_date"] == "2025-10-21"
    assert Decimal(readings[0]["start_value"]) == Decimal("1000.000")
    assert readings[0]["end_date"] == "2026-10-22"
    assert Decimal(readings[0]["end_value"]) == Decimal("1150.500")


def test_category_summary_start_fallback_first_reading_in_range(client):
    """No reading before the range start (meter installed mid-period):
    the first reading within the range is the start basis."""
    meter_id = _create_meter(client, "electricity_import", "Neu installiert")
    _create_reading(client, meter_id, "500.000", "2024-06-01")
    _create_reading(client, meter_id, "600.000", "2024-09-01")
    _create_tariff(client, meter_id, "2024-01-01", None, "0.30000",
                   base_fee_monthly="10.00")

    response = _get_summary(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()

    electricity = data["electricity"]
    assert Decimal(electricity["consumption"]) == Decimal("100.000")
    readings = electricity["readings"]
    assert readings[0]["start_date"] == "2024-06-01"
    assert Decimal(readings[0]["start_value"]) == Decimal("500.000")


def test_category_summary_from_after_to(client):
    """422 when from > to."""
    response = _get_summary(client, "2024-03-10", "2024-01-10")
    assert response.status_code == 422
    assert "Ungültiger Zeitraum" in response.json()["detail"]


def test_category_summary_query_parameter_alias(client):
    """The endpoint is exposed under query names 'from' and 'to'."""
    openapi = client.get("/api/openapi.json").json()
    params = openapi["paths"]["/api/costs/category-summary"]["get"]["parameters"]
    param_names = [p["name"] for p in params]

    assert sorted(param_names) == ["from", "to"]
