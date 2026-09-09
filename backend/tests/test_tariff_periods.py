"""
Tests for tariff period-related API endpoints.
"""
from decimal import Decimal


def test_create_tariff_period(client, sample_meter_data, sample_tariff_period_data):
    """Test creating a new tariff period."""
    # First create a meter
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # Update tariff period data with the created meter_id
    tariff_data = sample_tariff_period_data.copy()
    tariff_data["meter_id"] = meter_id
    
    response = client.post("/api/tariffs/", json=tariff_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == 1
    assert data["meter_id"] == meter_id
    # tariff_kind omitted in payload -> defaults to consumption
    assert data["tariff_kind"] == "consumption"
    assert data["valid_from"] == tariff_data["valid_from"]
    assert data["valid_to"] == tariff_data["valid_to"]
    assert Decimal(data["price_per_unit"]) == Decimal(tariff_data["price_per_unit"])
    assert Decimal(data["base_fee_monthly"]) == Decimal(tariff_data["base_fee_monthly"])


def test_create_tariff_period_without_fee(client, sample_meter_data):
    """Test creating a tariff period without optional base_fee_monthly."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = {
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": None,  # No end date (valid indefinitely)
        "price_per_unit": "0.35490"
        # base_fee_monthly omitted
    }
    
    response = client.post("/api/tariffs/", json=tariff_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["base_fee_monthly"] is None
    assert data["valid_to"] is None


def test_create_tariff_period_invalid_meter(client):
    """Test creating tariff period for non-existent meter."""
    tariff_data = {
        "meter_id": 999,
        "valid_from": "2024-01-01",
        "price_per_unit": "0.35490"
    }
    
    response = client.post("/api/tariffs/", json=tariff_data)
    
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "Meter not found" in response.json()["detail"]


def test_create_tariff_period_duplicate_valid_from(client, sample_meter_data):
    """Test creating tariff period with duplicate valid_from for same meter.

    Same valid_from always overlaps (lower bound inclusive), so the EXCLUDE
    constraint now rejects this instead of the old UNIQUE constraint.
    """
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = {
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "price_per_unit": "0.35490"
    }
    
    # First tariff period
    response1 = client.post("/api/tariffs/", json=tariff_data)
    assert response1.status_code == 200
    
    # Second tariff period with same valid_from
    response2 = client.post("/api/tariffs/", json=tariff_data)
    # Should fail with 409 Conflict
    assert response2.status_code == 409
    assert "detail" in response2.json()
    # Accept both specific and generic messages for compatibility
    assert response2.json()["detail"] in [
        (
            "Für diesen Zähler und diese Tarifart überschneidet sich der Zeitraum "
            "mit einem bestehenden Eintrag."
        ),
        "Der Vorgang verletzt eine Datenbank-Beschränkung."
    ]


def test_read_tariff_periods_empty(client):
    """Test reading tariff periods from empty database."""
    response = client.get("/api/tariffs/")
    
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_read_tariff_periods_with_data(client, sample_meter_data, sample_tariff_period_data):
    """Test reading tariff periods after creating one."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = sample_tariff_period_data.copy()
    tariff_data["meter_id"] = meter_id
    client.post("/api/tariffs/", json=tariff_data)
    
    response = client.get("/api/tariffs/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert Decimal(data[0]["price_per_unit"]) == Decimal(tariff_data["price_per_unit"])


def test_read_single_tariff_period(client, sample_meter_data, sample_tariff_period_data):
    """Test reading a specific tariff period by ID."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = sample_tariff_period_data.copy()
    tariff_data["meter_id"] = meter_id
    create_response = client.post("/api/tariffs/", json=tariff_data)
    period_id = create_response.json()["id"]
    
    response = client.get(f"/api/tariffs/{period_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == period_id
    assert Decimal(data["price_per_unit"]) == Decimal(tariff_data["price_per_unit"])


def test_read_nonexistent_tariff_period(client):
    """Test reading a tariff period that doesn't exist."""
    response = client.get("/api/tariffs/999")
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_update_tariff_period(client, sample_meter_data, sample_tariff_period_data):
    """Test updating an existing tariff period."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = sample_tariff_period_data.copy()
    tariff_data["meter_id"] = meter_id
    create_response = client.post("/api/tariffs/", json=tariff_data)
    period_id = create_response.json()["id"]
    
    update_data = {
        "price_per_unit": "0.50000",
        "base_fee_monthly": "15.00",
        "valid_to": "2025-12-31"
    }
    
    response = client.put(f"/api/tariffs/{period_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["price_per_unit"]) == Decimal(update_data["price_per_unit"])
    assert Decimal(data["base_fee_monthly"]) == Decimal(update_data["base_fee_monthly"])
    assert data["valid_to"] == update_data["valid_to"]


def test_update_nonexistent_tariff_period(client):
    """Test updating a tariff period that doesn't exist."""
    update_data = {"price_per_unit": "0.50000"}
    
    response = client.put("/api/tariffs/999", json=update_data)
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_delete_tariff_period(client, sample_meter_data, sample_tariff_period_data):
    """Test deleting a tariff period."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data = sample_tariff_period_data.copy()
    tariff_data["meter_id"] = meter_id
    create_response = client.post("/api/tariffs/", json=tariff_data)
    period_id = create_response.json()["id"]
    
    response = client.delete(f"/api/tariffs/{period_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Tariff period deleted" in data["message"]
    
    # Verify tariff period is deleted
    get_response = client.get(f"/api/tariffs/{period_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_tariff_period(client):
    """Test deleting a tariff period that doesn't exist."""
    response = client.delete("/api/tariffs/999")
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_create_adjacent_tariff_periods_ok(client, sample_meter_data):
    """Adjacent periods without overlap must both be accepted.

    valid_to is inclusive, so the next period must start the day after.
    """
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # First tariff period: 2024-01-01 .. 2024-12-31 (inclusive)
    tariff_data1 = {
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.35490"
    }
    
    # Second tariff period starts directly after: 2025-01-01 ..
    tariff_data2 = {
        "meter_id": meter_id,
        "valid_from": "2025-01-01",
        "price_per_unit": "0.40000"
    }
    
    response1 = client.post("/api/tariffs/", json=tariff_data1)
    assert response1.status_code == 200
    
    response2 = client.post("/api/tariffs/", json=tariff_data2)
    assert response2.status_code == 200


def test_create_tariff_period_same_kind_overlap_conflict(client, sample_meter_data):
    """Overlapping periods with the same tariff_kind must be rejected with 409."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data1 = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.35490"
    }
    
    # Overlaps 2024-06-01..2024-08-31 within the same tariff_kind
    tariff_data2 = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2024-06-01",
        "valid_to": "2024-08-31",
        "price_per_unit": "0.40000"
    }
    
    response1 = client.post("/api/tariffs/", json=tariff_data1)
    assert response1.status_code == 200
    
    response2 = client.post("/api/tariffs/", json=tariff_data2)
    assert response2.status_code == 409
    assert response2.json()["detail"] == (
        "Für diesen Zähler und diese Tarifart überschneidet sich der Zeitraum "
        "mit einem bestehenden Eintrag."
    )


def test_create_tariff_period_different_kind_identical_range_ok(client, sample_meter_data):
    """Different tariff_kind values may use identical ranges (parallel components)."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    tariff_data1 = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.35490"
    }
    
    tariff_data2 = {
        "meter_id": meter_id,
        "tariff_kind": "feed_in",
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.08200"
    }
    
    # The API returns 200 for successful creates (no 201 configured)
    response1 = client.post("/api/tariffs/", json=tariff_data1)
    assert response1.status_code == 200
    assert response1.json()["tariff_kind"] == "consumption"
    
    response2 = client.post("/api/tariffs/", json=tariff_data2)
    assert response2.status_code == 200
    assert response2.json()["tariff_kind"] == "feed_in"


def test_create_open_ended_period_conflicts_with_later_period(client, sample_meter_data):
    """An open-ended period (valid_to = NULL) must conflict with any later period
    of the same tariff_kind: daterange(valid_from, NULL, '[]') is unbounded above."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # Open-ended period
    tariff_data1 = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2024-01-01",
        "valid_to": None,
        "price_per_unit": "0.35490"
    }
    
    # Later period overlaps the unbounded open-ended one
    tariff_data2 = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2025-01-01",
        "price_per_unit": "0.40000"
    }
    
    response1 = client.post("/api/tariffs/", json=tariff_data1)
    assert response1.status_code == 200
    
    response2 = client.post("/api/tariffs/", json=tariff_data2)
    assert response2.status_code == 409
    assert response2.json()["detail"] == (
        "Für diesen Zähler und diese Tarifart überschneidet sich der Zeitraum "
        "mit einem bestehenden Eintrag."
    )


def test_filter_tariff_periods_by_tariff_kind(client, sample_meter_data):
    """GET /api/tariffs/?tariff_kind=... must filter by kind."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    consumption_data = {
        "meter_id": meter_id,
        "tariff_kind": "consumption",
        "valid_from": "2024-01-01",
        "price_per_unit": "0.35490"
    }
    feed_in_data = {
        "meter_id": meter_id,
        "tariff_kind": "feed_in",
        "valid_from": "2024-01-01",
        "price_per_unit": "0.08200"
    }
    
    consumption_response = client.post("/api/tariffs/", json=consumption_data)
    assert consumption_response.status_code == 200
    feed_in_response = client.post("/api/tariffs/", json=feed_in_data)
    assert feed_in_response.status_code == 200
    consumption_id = consumption_response.json()["id"]
    feed_in_id = feed_in_response.json()["id"]
    
    # Without filter: both are returned
    all_response = client.get("/api/tariffs/")
    assert all_response.status_code == 200
    assert len(all_response.json()) == 2
    
    # Filtered: only feed_in
    filtered_response = client.get("/api/tariffs/?tariff_kind=feed_in")
    assert filtered_response.status_code == 200
    data = filtered_response.json()
    assert len(data) == 1
    assert data[0]["id"] == feed_in_id
    assert data[0]["tariff_kind"] == "feed_in"
    assert data[0]["id"] != consumption_id
    
    # Filter for the other kind
    consumption_filtered = client.get("/api/tariffs/?tariff_kind=consumption")
    assert consumption_filtered.status_code == 200
    assert len(consumption_filtered.json()) == 1
    assert consumption_filtered.json()[0]["tariff_kind"] == "consumption"


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"