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


def _create_tariff(client, meter_id, valid_from, valid_to, price_per_unit, base_fee_monthly="12.50"):
    """Create a consumption tariff period via the API."""
    payload = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "price_per_unit": price_per_unit,
    }
    if base_fee_monthly is not None:
        payload["base_fee_monthly"] = base_fee_monthly
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
    # Base fee: 10.00 * 45/30 = 15.00
    # Total actual cost: 58.6956 + 15.00 = 73.6956 ≈ 73.70
    assert Decimal(data["actual_cost_to_date"]) == Decimal("73.70")
    
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
    assert data["message"] == "Kein aktiver Tarif für dieses Datum gefunden."


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
    # Base fee: 12.00 * 364/30 = 145.60 (Jan 1 to Dec 31 exclusive = 364 days)
    # Total: 350.00 + 145.60 = 495.60
    assert Decimal(data["projected_annual_cost"]) == Decimal("495.60")


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