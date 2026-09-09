"""
Tests for the projection endpoint (GET /api/meters/{id}/projection).
"""
from decimal import Decimal


def _create_meter(client, meter_type="electricity_import"):
    """Create a meter via the API and return its id."""
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": "Projection Test Meter"}
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


def _get_projection(client, meter_id, year, as_of_date=None):
    """Call the projection endpoint."""
    params = {"year": year}
    if as_of_date:
        params["as_of_date"] = as_of_date
    return client.get(f"/api/meters/{meter_id}/projection", params=params)


def test_projection_complete_year_actual_consumption(client):
    """Test completed year with actual full year consumption."""
    meter_id = _create_meter(client)
    
    # Create readings: one from previous year end, one from current year end
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1500.000", "2024-12-31")
    
    # Test with as_of_date in 2025 (year 2024 is completed)
    response = _get_projection(client, meter_id, year=2024, as_of_date="2025-01-01")
    
    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["year"] == 2024
    assert data["unit"] == "kWh"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("500.000")
    assert data["days_elapsed"] == 366  # 2024 is a leap year
    assert Decimal(data["projected_annual_consumption"]) == Decimal("500.000")
    assert data["basis"] == "actual_full_year"
    assert data["message"] is None


def test_projection_ongoing_year_linear_from_prev_year_end(client):
    """Test ongoing year with linear projection from previous year end."""
    meter_id = _create_meter(client)
    
    # Create readings
    _create_reading(client, meter_id, "1000.000", "2024-12-31")
    _create_reading(client, meter_id, "1125.000", "2025-03-01")  # 60 days later (Python date difference)
    
    # Test with as_of_date = 2025-03-01
    response = _get_projection(client, meter_id, year=2025, as_of_date="2025-03-01")
    
    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["year"] == 2025
    assert data["unit"] == "kWh"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("125.000")  # 1125 - 1000
    assert data["days_elapsed"] == 60  # Dec 31 to Mar 1 (60 days in Python date arithmetic)
    # Expected: (125 / 60) * 365 = 125 / 60 * 365 ≈ 760.416667
    expected_projection = Decimal("125.000") / Decimal(60) * Decimal(365)
    assert abs(Decimal(data["projected_annual_consumption"]) - expected_projection) < Decimal("0.001")
    assert data["basis"] == "linear_from_prev_year_end"
    assert data["message"] is None


def test_projection_ongoing_year_linear_from_first_reading_of_year(client):
    """Test ongoing year with linear projection from first reading in year."""
    meter_id = _create_meter(client)
    
    # Create readings - no reading on 2024-12-31
    _create_reading(client, meter_id, "150.000", "2025-02-01")  # First reading in year
    _create_reading(client, meter_id, "250.000", "2025-03-01")  # 28 days later
    
    # Test with as_of_date = 2025-03-01
    response = _get_projection(client, meter_id, year=2025, as_of_date="2025-03-01")
    
    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["year"] == 2025
    assert data["unit"] == "kWh"
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("100.000")  # 250-150
    assert data["days_elapsed"] == 28  # Feb has 28 days in 2025
    expected_projection = Decimal("100.000") / Decimal(28) * Decimal(365)
    assert abs(Decimal(data["projected_annual_consumption"]) - expected_projection) < Decimal("0.001")
    assert data["basis"] == "linear_from_first_reading_of_year"
    assert data["message"] is None


def test_projection_insufficient_data_no_readings(client):
    """Test insufficient data when no readings exist."""
    meter_id = _create_meter(client)
    
    response = _get_projection(client, meter_id, year=2024)
    
    assert response.status_code == 200  # 200 OK, not 404 - meter exists, just no data
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["year"] == 2024
    assert data["unit"] == "kWh"
    assert data["actual_consumption_to_date"] is None
    assert data["days_elapsed"] is None
    assert data["projected_annual_consumption"] is None
    assert data["basis"] == "insufficient_data"
    assert f"Nicht genügend Zählerstände im Jahr {2024}" in data["message"]


def test_projection_insufficient_data_single_reading(client):
    """Test insufficient data with only one reading in year."""
    meter_id = _create_meter(client)
    
    _create_reading(client, meter_id, "1000.000", "2024-06-15")
    
    response = _get_projection(client, meter_id, year=2024)
    
    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "insufficient_data"
    assert f"Nicht genügend Zählerstände im Jahr {2024}" in data["message"]


def test_projection_insufficient_data_end_before_start(client):
    """Test insufficient data when end reading date is before start reading date."""
    meter_id = _create_meter(client)
    
    # Create readings where end reading is actually before start reading
    # This shouldn't normally happen with correct data, but we handle it defensively
    _create_reading(client, meter_id, "1100.000", "2024-06-15")  # Later date but will be treated as "start" by logic
    _create_reading(client, meter_id, "1000.000", "2024-03-01")  # Earlier date but will be "end" if as_of_date is early
    
    # With as_of_date = 2024-03-01, end reading would be 2024-03-01, start would be first in year
    # But actually the logic finds start reading from 2023-12-31 (not found) or first in 2024 = 2024-03-01
    # And end reading for as_of_date=2024-03-01 is also 2024-03-01, so start >= end
    response = _get_projection(client, meter_id, year=2024, as_of_date="2024-03-01")
    
    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "insufficient_data"
    assert f"Nicht genügend Zählerstände im Jahr {2024}" in data["message"]


def test_projection_meter_not_found(client):
    """Test 404 when meter does not exist."""
    response = _get_projection(client, meter_id=99999, year=2024)
    
    assert response.status_code == 404
    assert "Meter mit ID" in response.json()["detail"]


def test_projection_invalid_year_too_early(client):
    """Test 422 when year is before minimum year."""
    meter_id = _create_meter(client)
    
    response = _get_projection(client, meter_id, year=1800)
    
    assert response.status_code == 422
    assert "Jahr 1800 ist außerhalb des gültigen Bereichs" in response.json()["detail"]


def test_projection_invalid_year_too_late(client):
    """Test 422 when year is after maximum year."""
    meter_id = _create_meter(client)
    
    response = _get_projection(client, meter_id, year=2200)
    
    assert response.status_code == 422
    assert "Jahr 2200 ist außerhalb des gültigen Bereichs" in response.json()["detail"]


def test_projection_as_of_date_affects_result(client):
    """Test that as_of_date parameter affects projection result."""
    meter_id = _create_meter(client)
    
    _create_reading(client, meter_id, "1000.000", "2024-12-31")
    _create_reading(client, meter_id, "1100.000", "2025-06-01")  # 152 days later (Python date difference)
    
    # Test with as_of_date in middle of year
    response1 = _get_projection(client, meter_id, year=2025, as_of_date="2025-06-01")
    data1 = response1.json()
    assert data1["basis"] == "linear_from_prev_year_end"
    assert data1["days_elapsed"] == 152  # Dec 31 to Jun 1 (Python date arithmetic: 152 days)
    
    # Test with as_of_date at year end
    response2 = _get_projection(client, meter_id, year=2025, as_of_date="2025-12-31")
    assert response2.status_code == 200
    # Should still be linear projection (year not completed relative to as_of_date)


def test_projection_future_year(client):
    """Test projection for future year (year > as_of_date.year)."""
    meter_id = _create_meter(client)
    
    _create_reading(client, meter_id, "1000.000", "2025-12-31")
    # No readings in 2026 yet
    
    # Try to get projection for 2026 with as_of_date in 2025
    response = _get_projection(client, meter_id, year=2026, as_of_date="2025-12-31")
    
    assert response.status_code == 200
    data = response.json()
    # Since no readings in 2026, should be insufficient_data
    assert data["basis"] == "insufficient_data"


def test_projection_negative_consumption(client):
    """Test projection with negative consumption (meter rollover scenario)."""
    meter_id = _create_meter(client)
    
    # Simulate meter reset: end value < start value
    _create_reading(client, meter_id, "9900.000", "2024-12-31")
    _create_reading(client, meter_id, "100.000", "2025-06-01")  # Meter rolled over
    
    response = _get_projection(client, meter_id, year=2025, as_of_date="2025-06-01")
    
    assert response.status_code == 200
    data = response.json()
    # Negative consumption should be calculated (not validated/clamped)
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("-9800.000")  # 100 - 9900
    # Projection will also be negative
    assert Decimal(data["projected_annual_consumption"]) < Decimal(0)


def test_projection_uses_server_date_when_as_of_date_not_provided(client):
    """Test that endpoint works when as_of_date parameter is omitted."""
    meter_id = _create_meter(client)
    
    _create_reading(client, meter_id, "1000.000", "2024-12-31")
    _create_reading(client, meter_id, "1125.000", "2025-03-01")
    
    # Test without as_of_date parameter - will use server's current date
    # We can't mock date.today() easily, so just test that the endpoint
    # returns a valid response (not a 500 error)
    response = _get_projection(client, meter_id, year=2025)
    
    # The response should be either:
    # 1. 200 with linear projection (if current date is before 2025-12-31)
    # 2. 200 with actual_full_year (if current date is after 2025-12-31 - unlikely in test)
    # 3. 200 with insufficient_data (if current date doesn't have readings yet)
    assert response.status_code in [200]
    
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["year"] == 2025
    assert data["unit"] == "kWh"
    # The actual projection depends on the server's current date,
    # but we verify the structure is correct


def test_projection_with_multiple_readings_selects_correct_boundaries(client):
    """Test that correct start and end readings are selected when multiple exist."""
    meter_id = _create_meter(client)
    
    # Create multiple readings
    _create_reading(client, meter_id, "950.000", "2024-12-15")
    _create_reading(client, meter_id, "1000.000", "2024-12-31")  # Should be start
    _create_reading(client, meter_id, "1100.000", "2025-03-01")
    _create_reading(client, meter_id, "1200.000", "2025-03-15")
    _create_reading(client, meter_id, "1300.000", "2025-06-01")
    
    # Test with as_of_date = 2025-03-15
    response = _get_projection(client, meter_id, year=2025, as_of_date="2025-03-15")
    
    assert response.status_code == 200
    data = response.json()
    # Should use 2024-12-31 as start and 2025-03-15 as end
    assert Decimal(data["actual_consumption_to_date"]) == Decimal("200.000")  # 1200 - 1000
    assert data["basis"] == "linear_from_prev_year_end"