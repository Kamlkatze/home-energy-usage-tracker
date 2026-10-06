"""
Tests for the yearly projection with cost endpoint (GET /api/costs/yearly-projection).
"""
from datetime import UTC, datetime
from decimal import Decimal


def _create_meter(client, meter_type="electricity_import"):
    """Create a meter via the API and return its id."""
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": "Yearly Cost Test Meter"}
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_reading(client, meter_id, value, reading_date):
    """Create a reading via the API."""
    response = client.post(
        "/api/readings/",
        json={"meter_id": meter_id, "value": value, "reading_date": reading_date},
    )
    assert response.status_code == 200


def _create_tariff(client, meter_id, valid_from, valid_to, price_per_unit, base_fee_monthly="12.50", gas_z_zahl=None, gas_brennwert=None):
    """Create a consumption tariff period via the API.

    base_fee_monthly=None omits the field so the tariff has no base fee.
    gas_z_zahl/gas_brennwert are only included when explicitly provided.
    """
    payload = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "price_per_unit": price_per_unit,
    }
    if base_fee_monthly is not None:
        payload["base_fee_monthly"] = base_fee_monthly
    if gas_z_zahl is not None:
        payload["gas_z_zahl"] = gas_z_zahl
    if gas_brennwert is not None:
        payload["gas_brennwert"] = gas_brennwert
    response = client.post("/api/tariffs/", json=payload)
    assert response.status_code == 200


def calculate_yearly_projection(client, meter_id, year, as_of_date=None):
    """Call the yearly projection with cost endpoint."""
    params = {"meter_id": meter_id, "year": year}
    if as_of_date is not None:
        params["as_of_date"] = as_of_date
    return client.get("/api/costs/yearly-projection", params=params)


def test_yearly_projection_with_cost_basic_case(client):
    """Test basic case: ongoing year with readings and active tariff."""
    meter_id = _create_meter(client)
    
    # Create readings for previous year end and current year
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")  # as_of_date reading
    
    # Create active tariff for 2024
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    
    # Calculate yearly projection with cost for 2024 as of Feb 15
    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check projection data
    assert data["meter_id"] == meter_id
    assert data["year"] == 2024
    assert data["unit"] == "kWh"
    assert data["as_of_date"] == "2024-02-15"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("200.000")  # 1200 - 1000
    assert data["basis"] == "linear_from_prev_year_end"
    
    # Check cost calculations
    # Actual cost to date: Jan 1 to Feb 15 (45 days, exclusive end)
    # Consumption from Dec 31 to Feb 15: 200 over 46 days
    # Prorated for Jan 1 to Feb 15: 200 * 45/46 = 195.652
    # Energy cost: 195.652 * 0.30 = 58.6956
    # Base fee: Jan full (31/31) + Feb 1-14 (14/29) = 10.00 + 10.00*14/29 = 14.8276
    # Total actual cost: 58.6956 + 14.8276 = 73.5232 → 73.52
    assert Decimal(data["actual_cost_to_date"]) == Decimal("73.52")
    
    # Projected annual consumption: (200 / 46) * 365 ≈ 1586.9565
    # Projected energy cost: 1586.9565 * 0.30 = 476.08695
    # Projected base fee: 10.00 * 365/30 = 121.6667 ≈ 121.67 (full year, 365 days)
    # Total projected cost: 476.08695 + 121.6667 ≈ 597.75
    # But actually for ongoing year, we use base_fee_monthly * 12 = 120.00
    # Energy cost: 1586.9565 * 0.30 = 476.08695
    # Total: 476.08695 + 120.00 = 596.08695 ≈ 596.09
    assert Decimal(data["projected_annual_cost"]) == Decimal("596.09")
    assert data["message"] is None


def test_yearly_projection_no_active_tariff(client):
    """Test case where no active tariff exists for as_of_date."""
    meter_id = _create_meter(client)
    
    # Create readings
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    
    # Create tariff that ended before as_of_date
    _create_tariff(
        client,
        meter_id,
        valid_from="2023-01-01",
        valid_to="2023-12-31",
        price_per_unit="0.25000",
        base_fee_monthly="8.00",
    )
    
    response = calculate_yearly_projection(client, meter_id, 2024, "2024-01-15")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should still return projection data
    assert data["meter_id"] == meter_id
    assert data["projected_annual_consumption"] is not None
    assert data["basis"] == "linear_from_prev_year_end"
    
    # But no projected cost because no active tariff
    assert data["projected_annual_cost"] is None
    # Both the actual-cost path (no tariff covering Jan 1 - Jan 15) and the
    # projected path (no active tariff) fail; both reasons are concatenated
    # into the single message field.
    assert data["message"] == (
        "Kein gültiger Tarif für diesen Zeitraum gefunden. "
        "Kein aktiver Tarif für dieses Datum gefunden."
    )


def test_yearly_projection_insufficient_data(client):
    """Test case where insufficient data for projection."""
    meter_id = _create_meter(client)
    
    # Create only one reading in the year
    _create_reading(client, meter_id, "1000.000", "2024-01-15")
    
    # Create tariff
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    
    response = calculate_yearly_projection(client, meter_id, 2024, "2024-01-15")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["basis"] == "insufficient_data"
    assert data["projected_annual_consumption"] is None
    assert data["projected_annual_cost"] is None
    assert data["message"] is not None  # Should have explanation message


def test_yearly_projection_completed_year(client):
    """Test case for completed year (actual_full_year basis)."""
    meter_id = _create_meter(client)
    
    # Create readings for completed year 2023
    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    
    # Create tariff for 2023
    _create_tariff(
        client,
        meter_id,
        valid_from="2023-01-01",
        valid_to="2023-12-31",
        price_per_unit="0.35000",
        base_fee_monthly="12.00",
    )
    
    # Test for completed year 2023 as of 2024-01-15
    response = calculate_yearly_projection(client, meter_id, 2023, "2024-01-15")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["basis"] == "actual_full_year"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("1000.000")  # 2000 - 1000
    assert Decimal(data["projected_annual_consumption"]) == Decimal("1000.000")  # Same as actual for completed year
    
    # Actual cost for full year: consumption 1000 * 0.35 = 350.00
    # Base fee: 12.00 * (11 + 30/31) = 143.6129 (Jan 1 to Dec 31 exclusive = 364 days)
    # Total: 350.00 + 143.61 = 493.61
    assert Decimal(data["projected_annual_cost"]) == Decimal("493.61")

    # Actual cost path: prorated consumption 1000 * 364/365 = 997.2602...
    # Energy cost: 997.2602... * 0.35 = 349.0411...
    # Base fee: 12.00 * (11 + 30/31) = 143.6129...
    # Total: 492.6540... -> 492.65
    assert Decimal(data["actual_cost_to_date"]) == Decimal("492.65")


def test_yearly_projection_completed_year_reading_after_year_end(client):
    """Regression: a reading AFTER the completed year must not inflate costs.

    Completed year 2023, viewed as of 2024-06-30. Without the Dec 31 clamp
    the end reading (2024-06-30) pulled 2024 consumption and ~1.5 years of
    base fee into the 2023 actual cost.

    Readings: 1000.000 (2022-12-31), 2000.000 (2023-12-31),
              2600.000 (2024-06-30, after the viewed year)
    Tariff 2023-01-01..2023-12-31: price 0.35000, base_fee_monthly 12.00

    With the clamp, the end reading is 2023-12-31:
      total_consumption = 1000.000 over 365 days
      cost period [2023-01-01, 2023-12-31) = 364 days overlap
      prorated = 1000.000 * 364/365 = 997.2602...
      Energy cost: 997.2602... * 0.35 = 349.0411...
      Base fee: 12.00 * (11 + 30/31) = 143.6129...
      Total: 492.6540... -> 492.65 (identical to no-later-reading case)
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    _create_reading(client, meter_id, "2600.000", "2024-06-30")

    _create_tariff(
        client,
        meter_id,
        valid_from="2023-01-01",
        valid_to="2023-12-31",
        price_per_unit="0.35000",
        base_fee_monthly="12.00",
    )

    response = calculate_yearly_projection(client, meter_id, 2023, "2024-06-30")

    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "actual_full_year"
    # Projection for completed years is year-bounded anyway.
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("1000.000")
    assert Decimal(data["projected_annual_consumption"]) == Decimal("1000.000")
    assert Decimal(data["projected_annual_cost"]) == Decimal("493.61")
    # The actual cost must equal the full-2023 cost, NOT the multi-year one.
    assert Decimal(data["actual_cost_to_date"]) == Decimal("492.65")
    assert data["message"] is None


def test_yearly_projection_completed_year_gas_reading_after_year_end(client):
    """Regression (gas): a later reading must not inflate the 2023 gas cost.

    Gas meter, completed year 2023 viewed as of 2024-06-30 with a reading on
    2024-06-30. Tariff 2023: price 0.10000 €/kWh, no base fee,
    gas_z_zahl 0.9612, gas_brennwert 11.482.

    With the clamp, end reading is 2023-12-31:
      prorated = 1000.000 * 364/365 = 997.2602... m³
      kWh = 997.2602... * 0.9612 * 11.482 = 11006.2614...
      cost = 11006.2614... * 0.10000 = 1100.6261... -> 1100.63
    """
    meter_id = _create_meter(client, meter_type="gas")

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    _create_reading(client, meter_id, "2600.000", "2024-06-30")

    _create_tariff(
        client,
        meter_id,
        valid_from="2023-01-01",
        valid_to="2023-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = calculate_yearly_projection(client, meter_id, 2023, "2024-06-30")

    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "actual_full_year"
    assert Decimal(data["actual_cost_to_date"]) == Decimal("1100.63")
    assert Decimal(data["projected_annual_cost"]) == Decimal("1103.65")
    assert data["message"] is None


def test_yearly_projection_meter_not_found(client):
    """Test 404 when meter doesn't exist."""
    response = calculate_yearly_projection(client, 999999, 2024)
    
    assert response.status_code == 404
    assert "Meter mit ID" in response.json()["detail"]


def test_yearly_projection_invalid_year(client):
    """Test 422 when year is out of valid range."""
    meter_id = _create_meter(client)
    
    # Test year too early
    response = calculate_yearly_projection(client, meter_id, 1999)
    assert response.status_code == 422
    assert "Jahr" in response.json()["detail"]
    
    # Test year too late
    response = calculate_yearly_projection(client, meter_id, 2101)
    assert response.status_code == 422
    assert "Jahr" in response.json()["detail"]


def test_yearly_projection_multiple_tariff_periods(client):
    """Test with multiple tariff periods within the year."""
    meter_id = _create_meter(client)
    
    # Create readings
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-31")
    _create_reading(client, meter_id, "1250.000", "2024-03-15")  # as_of_date
    
    # Create multiple tariff periods in 2024
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-01-31",
        price_per_unit="0.25000",
        base_fee_monthly="8.00",
    )
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-01",
        valid_to=None,  # Open-ended
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    
    response = calculate_yearly_projection(client, meter_id, 2024, "2024-03-15")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should use tariff active on as_of_date (second tariff)
    assert data["projected_annual_cost"] is not None
    
    # Calculate with second tariff's rates
    # Projected consumption (from first test): (250 / 75) * 365 ≈ 1216.6667
    # Price: 0.30 per unit, base fee: 10.00 monthly
    # Energy cost: 1216.6667 * 0.30 = 365.00001
    # Base fee: 10.00 * 12 = 120.00
    # Total: 365.00 + 120.00 = 485.00
    assert Decimal(data["projected_annual_cost"]) == Decimal("485.00")


def test_yearly_projection_default_as_of_date(client):
    """Test that as_of_date defaults to today when not provided."""
    meter_id = _create_meter(client)
    
    # Create minimal data to avoid errors
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", datetime.now(UTC).date().isoformat())
    
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    
    response = calculate_yearly_projection(client, meter_id, 2024)
    
    # Should succeed with default date
    assert response.status_code == 200
    data = response.json()
    assert data["as_of_date"] == datetime.now(UTC).date().isoformat()


def test_yearly_projection_gas_ongoing_year(client):
    """Gas meter (ongoing year): m³ consumption converted to kWh for actual
    and projected costs.

    Readings: 1000.000 (2023-12-31), 1100.000 (2024-01-15), 1200.000 (2024-02-15)
    Tariff 2024-01-01..2024-12-31: price 0.10000 €/kWh, no base fee,
      gas_z_zahl = 0.9612, gas_brennwert = 11.482

    Projection: actual = 200.000 m³ over 46 days
      projected_annual = 200/46 * 365 ≈ 1586.9565 m³ (stays in m³)

    Actual cost to date [2024-01-01, 2024-02-15):
      prorated = 200.000 * 45/46 = 195.6521... m³
      kWh = 195.6521... * 0.9612 * 11.482 = 2159.3149... kWh
      cost = 2159.3149... * 0.10000 = 215.9314... -> 215.93

    Projected annual cost (active tariff, base fee 0):
      kWh = 1586.9565... * 0.9612 * 11.482 = 17514.4431... kWh
      cost = 17514.4431... * 0.10000 = 1751.4443... -> 1751.44
    """
    meter_id = _create_meter(client, meter_type="gas")

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "m³"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("200.000")
    assert data["basis"] == "linear_from_prev_year_end"
    # Consumption stays in m³; only the billing amounts are converted.
    assert Decimal(data["projected_annual_consumption"]) == Decimal(
        (Decimal("200.000") / Decimal(46)) * Decimal(365)
    )
    assert Decimal(data["actual_cost_to_date"]) == Decimal("215.93")
    assert Decimal(data["projected_annual_cost"]) == Decimal("1751.44")
    assert data["message"] is None


def test_yearly_projection_gas_missing_conversion_factors(client):
    """Gas tariff without gas_z_zahl/gas_brennwert degrades gracefully:
    200 OK, cost fields null, explanatory message (like "no active tariff")."""
    meter_id = _create_meter(client, meter_type="gas")

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
    )

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "linear_from_prev_year_end"
    assert data["actual_cost_to_date"] is None
    assert data["projected_annual_cost"] is None
    # Both the actual-cost and the projected-cost path fail on the same
    # missing fields; the combined message shows the reason only once.
    assert data["message"] == (
        "Gastarife benötigen die Felder gas_z_zahl und "
        "gas_brennwert zur Umrechnung von m³ in kWh."
    )


def test_yearly_projection_gas_completed_year(client):
    """Gas meter (completed year): both cost paths convert m³ to kWh.

    Readings: 1000.000 (2022-12-31), 1500.000 (2023-06-30), 2000.000 (2023-12-31)
    Tariff 2023-01-01..2023-12-31: price 0.10000 €/kWh, no base fee,
      gas_z_zahl = 0.9612, gas_brennwert = 11.482

    Projection: actual_full_year, 1000.000 m³ (stays in m³).

    Actual cost path [2023-01-01, 2023-12-31):
      prorated = 1000.000 * 364/365 = 997.2602... m³
      kWh = 997.2602... * 0.9612 * 11.482 = 11006.2614... kWh
      cost = 11006.2614... * 0.10000 = 1100.6261... -> 1100.63

    Projected cost (full year):
      kWh = 1000.000 * 0.9612 * 11.482 = 11036.4984 kWh
      cost = 11036.4984 * 0.10000 = 1103.6498... -> 1103.65
    """
    meter_id = _create_meter(client, meter_type="gas")

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client,
        meter_id,
        valid_from="2023-01-01",
        valid_to="2023-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = calculate_yearly_projection(client, meter_id, 2023, "2024-01-15")

    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "m³"
    assert data["basis"] == "actual_full_year"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("1000.000")
    assert Decimal(data["projected_annual_consumption"]) == Decimal("1000.000")
    assert Decimal(data["actual_cost_to_date"]) == Decimal("1100.63")
    assert Decimal(data["projected_annual_cost"]) == Decimal("1103.65")
    assert data["message"] is None


def test_yearly_projection_non_gas_unaffected_by_gas_fields(client):
    """Regression: gas conversion must NOT apply to non-gas meters.

    Same setup as the basic electricity test, but the tariff carries gas
    conversion fields. The expected costs must equal the basic case
    (raw kWh * price_per_unit), proving the conversion is skipped.
    """
    meter_id = _create_meter(client)  # electricity_import -> unit kWh

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "kWh"
    # Identical to test_yearly_projection_with_cost_basic_case:
    # no conversion applied despite gas fields on the tariff.
    assert Decimal(data["actual_cost_to_date"]) == Decimal("73.52")
    assert Decimal(data["projected_annual_cost"]) == Decimal("596.09")


def test_yearly_projection_actual_cost_missing_gas_factors(client):
    """Actual-cost path fails on missing gas factors, projected path succeeds.

    Gas meter with two tariff periods: the tariff covering January lacks
    gas_z_zahl/gas_brennwert (actual-cost path -> 422), while the open-ended
    tariff active on as_of_date (Feb 15) has them (projected path -> 1751.44).
    """
    meter_id = _create_meter(client, meter_type="gas")

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-01-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
    )
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-01",
        valid_to=None,
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["actual_cost_to_date"] is None
    # Projected path uses the active tariff (Feb 1, open-ended) with factors:
    # kWh = 1586.9565... m³ * 0.9612 * 11.482 = 17514.4431...
    # cost = 17514.4431... * 0.10000 = 1751.44
    assert Decimal(data["projected_annual_cost"]) == Decimal("1751.44")
    assert data["message"] == (
        "Gastarife benötigen die Felder gas_z_zahl und "
        "gas_brennwert zur Umrechnung von m³ in kWh."
    )


def test_yearly_projection_actual_cost_missing_tariff(client):
    """Actual-cost path fails on a tariff gap, projected path succeeds.

    The consumption tariff only starts on Jan 15, leaving Jan 1 - Jan 14
    uncovered: the actual-cost path raises 404 ("Kein gültiger Tarif...")
    while the projected path uses the active tariff at as_of_date and
    computes a cost (596.09, identical to the basic electricity case).
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-15",
        valid_to=None,
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["actual_cost_to_date"] is None
    assert Decimal(data["projected_annual_cost"]) == Decimal("596.09")
    assert data["message"] == "Kein gültiger Tarif für diesen Zeitraum gefunden."


def test_yearly_projection_both_paths_fail_different_reasons(client):
    """Both cost paths fail with different reasons: messages concatenated.

    Electricity meter with no tariff at all: the actual-cost path cannot
    find a tariff for Jan 1 - Feb 15 ("...für diesen Zeitraum...") and the
    projected path has no active tariff at as_of_date ("...für dieses
    Datum..."). Both reasons are shown, space-separated.
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-01-15")
    _create_reading(client, meter_id, "1200.000", "2024-02-15")

    response = calculate_yearly_projection(client, meter_id, 2024, "2024-02-15")

    assert response.status_code == 200
    data = response.json()
    assert data["actual_cost_to_date"] is None
    assert data["projected_annual_cost"] is None
    assert data["message"] == (
        "Kein gültiger Tarif für diesen Zeitraum gefunden. "
        "Kein aktiver Tarif für dieses Datum gefunden."
    )