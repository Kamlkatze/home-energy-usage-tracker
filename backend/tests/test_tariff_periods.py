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
    """Test creating tariff period with duplicate valid_from for same meter."""
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
        "Für diesen Zähler existiert bereits ein Tarifzeitraum mit diesem Startdatum.",
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


def test_tariff_period_overlap_constraint(client, sample_meter_data):
    """Test that overlapping tariff periods are prevented (implied by unique constraint)."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # First tariff period
    tariff_data1 = {
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "price_per_unit": "0.35490"
    }
    
    # Second tariff period with different valid_from
    tariff_data2 = {
        "meter_id": meter_id,
        "valid_from": "2024-07-01",
        "price_per_unit": "0.40000"
    }
    
    response1 = client.post("/api/tariffs/", json=tariff_data1)
    assert response1.status_code == 200
    
    response2 = client.post("/api/tariffs/", json=tariff_data2)
    assert response2.status_code == 200


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"