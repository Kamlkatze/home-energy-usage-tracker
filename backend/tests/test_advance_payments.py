"""
Tests for advance payment-related API endpoints.
"""


def _create_meter(client, meter_type="gas"):
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": "Test Meter"}
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_create_advance_payment(client, sample_meter_data, sample_advance_payment_data):
    """Test creating a new advance payment."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id

    response = client.post("/api/advance-payments/", json=payment_data)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == 1
    assert data["meter_id"] == meter_id
    assert data["category"] == "gas"
    assert data["valid_from"] == payment_data["valid_from"]
    assert data["valid_to"] == payment_data["valid_to"]
    assert data["monthly_amount"] == payment_data["monthly_amount"]


def test_create_advance_payment_open_ended(client, sample_meter_data):
    """Test creating an advance payment without end date."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": None,
        "monthly_amount": "120.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)

    assert response.status_code == 200
    data = response.json()
    assert data["valid_to"] is None
    assert data["monthly_amount"] == "120.00"


def test_create_advance_payment_invalid_meter(client):
    """Test creating advance payment for non-existent meter."""
    payment_data = {
        "category": "gas",
        "meter_id": 999,
        "valid_from": "2024-01-01",
        "monthly_amount": "120.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)

    assert response.status_code == 404
    assert "Meter not found" in response.json()["detail"]


def test_create_advance_payment_wastewater(client):
    """Test creating a wastewater advance payment."""
    cold_meter_id = _create_meter(client, "water_cold")

    payment_data = {
        "category": "wastewater",
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "wastewater"
    assert data["water_cold_meter_id"] == cold_meter_id
    assert data["meter_id"] is None
    assert data["monthly_amount"] == "80.00"


def test_create_advance_payment_wastewater_with_garden(client):
    """Test creating a wastewater advance payment with garden meter."""
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")

    payment_data = {
        "category": "wastewater",
        "water_cold_meter_id": cold_meter_id,
        "water_garden_meter_id": garden_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 200
    data = response.json()
    assert data["water_garden_meter_id"] == garden_meter_id


def test_create_advance_payment_wastewater_meter_id_set(client):
    """WASTEWATER with meter_id set must be rejected (422)."""
    cold_meter_id = _create_meter(client, "water_cold")
    gas_meter_id = _create_meter(client, "gas")

    payment_data = {
        "category": "wastewater",
        "meter_id": gas_meter_id,
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 422
    assert "meter_id must be null for wastewater" in response.json()["detail"][0]["msg"]


def test_create_advance_payment_wastewater_no_cold_meter(client):
    """WASTEWATER without water_cold_meter_id must be rejected (422)."""
    payment_data = {
        "category": "wastewater",
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 422
    assert "water_cold_meter_id is required" in response.json()["detail"][0]["msg"]


def test_create_advance_payment_non_wastewater_no_meter_id(client):
    """Non-wastewater category without meter_id must be rejected (422)."""
    payment_data = {
        "category": "power_import",
        "valid_from": "2024-01-01",
        "monthly_amount": "120.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 422
    assert "meter_id is required" in response.json()["detail"][0]["msg"]


def test_create_advance_payment_non_wastewater_with_water_cold(client):
    """Non-wastewater with water_cold_meter_id set must be rejected (422)."""
    meter_id = _create_meter(client, "gas")
    cold_meter_id = _create_meter(client, "water_cold")

    payment_data = {
        "category": "gas",
        "meter_id": meter_id,
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "120.00"
    }

    response = client.post("/api/advance-payments/", json=payment_data)
    assert response.status_code == 422
    assert "water_cold_meter_id must be null" in response.json()["detail"][0]["msg"]


def test_read_advance_payments_empty(client):
    """Test reading advance payments from empty database."""
    response = client.get("/api/advance-payments/")

    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_read_advance_payments_with_data(client, sample_meter_data, sample_advance_payment_data):
    """Test reading advance payments after creating one."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id
    client.post("/api/advance-payments/", json=payment_data)

    response = client.get("/api/advance-payments/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["monthly_amount"] == payment_data["monthly_amount"]


def test_read_single_advance_payment(client, sample_meter_data, sample_advance_payment_data):
    """Test reading a specific advance payment by ID."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id
    create_response = client.post("/api/advance-payments/", json=payment_data)
    payment_id = create_response.json()["id"]

    response = client.get(f"/api/advance-payments/{payment_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == payment_id
    assert data["monthly_amount"] == payment_data["monthly_amount"]


def test_read_nonexistent_advance_payment(client):
    """Test reading an advance payment that doesn't exist."""
    response = client.get("/api/advance-payments/999")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_update_advance_payment(client, sample_meter_data, sample_advance_payment_data):
    """Test updating an existing advance payment."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id
    create_response = client.post("/api/advance-payments/", json=payment_data)
    payment_id = create_response.json()["id"]

    update_data = {
        "monthly_amount": "150.00",
        "valid_to": "2025-12-31"
    }

    response = client.put(f"/api/advance-payments/{payment_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["monthly_amount"] == update_data["monthly_amount"]
    assert data["valid_to"] == update_data["valid_to"]


def test_update_nonexistent_advance_payment(client):
    """Test updating an advance payment that doesn't exist."""
    update_data = {"monthly_amount": "150.00"}

    response = client.put("/api/advance-payments/999", json=update_data)

    assert response.status_code == 404
    assert "detail" in response.json()


def test_delete_advance_payment(client, sample_meter_data, sample_advance_payment_data):
    """Test deleting an advance payment."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id
    create_response = client.post("/api/advance-payments/", json=payment_data)
    payment_id = create_response.json()["id"]

    response = client.delete(f"/api/advance-payments/{payment_id}")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Advance payment deleted" in data["message"]

    get_response = client.get(f"/api/advance-payments/{payment_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_advance_payment(client):
    """Test deleting an advance payment that doesn't exist."""
    response = client.delete("/api/advance-payments/999")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_create_overlapping_advance_payments_rejected(client, sample_meter_data):
    """Overlapping advance payments for the same meter must be rejected with 409."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data1 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "120.00"
    }

    payment_data2 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-06-01",
        "valid_to": "2024-08-31",
        "monthly_amount": "150.00"
    }

    response1 = client.post("/api/advance-payments/", json=payment_data1)
    assert response1.status_code == 200

    response2 = client.post("/api/advance-payments/", json=payment_data2)
    assert response2.status_code == 409
    assert "detail" in response2.json()


def test_create_adjacent_advance_payments_ok(client, sample_meter_data):
    """Adjacent advance payments without overlap must both be accepted."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data1 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "120.00"
    }

    payment_data2 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2025-01-01",
        "monthly_amount": "150.00"
    }

    response1 = client.post("/api/advance-payments/", json=payment_data1)
    assert response1.status_code == 200

    response2 = client.post("/api/advance-payments/", json=payment_data2)
    assert response2.status_code == 200


def test_create_open_ended_advance_payment_conflicts_with_later(client, sample_meter_data):
    """An open-ended advance payment must conflict with any later period for same meter."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data1 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": None,
        "monthly_amount": "120.00"
    }

    payment_data2 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2025-01-01",
        "monthly_amount": "150.00"
    }

    response1 = client.post("/api/advance-payments/", json=payment_data1)
    assert response1.status_code == 200

    response2 = client.post("/api/advance-payments/", json=payment_data2)
    assert response2.status_code == 409
    assert "detail" in response2.json()


def test_create_overlapping_wastewater_rejected(client):
    """Overlapping wastewater payments for same water_cold_meter_id rejected."""
    cold_meter_id = _create_meter(client, "water_cold")

    payment_data1 = {
        "category": "wastewater",
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    payment_data2 = {
        "category": "wastewater",
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-06-01",
        "valid_to": "2024-08-31",
        "monthly_amount": "90.00"
    }

    response1 = client.post("/api/advance-payments/", json=payment_data1)
    assert response1.status_code == 200

    response2 = client.post("/api/advance-payments/", json=payment_data2)
    assert response2.status_code == 409


def test_filter_advance_payments_by_meter(client, sample_meter_data):
    """GET /api/advance-payments/?meter_id=... must filter by meter."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    meter_data2 = {
        "meter_type": "electricity_import",
        "label": "Main Electricity Meter",
    }
    meter_response2 = client.post("/api/meters/", json=meter_data2)
    meter_id2 = meter_response2.json()["id"]

    payment1 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "monthly_amount": "120.00"
    }
    payment2 = {
        "category": "power_import",
        "meter_id": meter_id2,
        "valid_from": "2024-01-01",
        "monthly_amount": "200.00"
    }

    client.post("/api/advance-payments/", json=payment1)
    client.post("/api/advance-payments/", json=payment2)

    all_response = client.get("/api/advance-payments/")
    assert all_response.status_code == 200
    assert len(all_response.json()) == 2

    filtered_response = client.get(f"/api/advance-payments/?meter_id={meter_id}")
    assert filtered_response.status_code == 200
    data = filtered_response.json()
    assert len(data) == 1
    assert data[0]["meter_id"] == meter_id


def test_filter_advance_payments_by_category(client, sample_meter_data):
    """GET /api/advance-payments/?category=... must filter by category."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    meter_data2 = {
        "meter_type": "electricity_import",
        "label": "Main Electricity Meter",
    }
    meter_response2 = client.post("/api/meters/", json=meter_data2)
    meter_id2 = meter_response2.json()["id"]

    payment1 = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "monthly_amount": "120.00"
    }
    payment2 = {
        "category": "power_import",
        "meter_id": meter_id2,
        "valid_from": "2024-01-01",
        "monthly_amount": "200.00"
    }

    client.post("/api/advance-payments/", json=payment1)
    client.post("/api/advance-payments/", json=payment2)

    filtered_response = client.get("/api/advance-payments/?category=power_import")
    assert filtered_response.status_code == 200
    data = filtered_response.json()
    assert len(data) == 1
    assert data[0]["category"] == "power_import"


def test_advance_payments_cascade_on_meter_delete(client, sample_meter_data, sample_advance_payment_data):
    """Deleting a meter must cascade delete its advance payments."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]

    payment_data = sample_advance_payment_data.copy()
    payment_data["meter_id"] = meter_id
    client.post("/api/advance-payments/", json=payment_data)

    client.delete(f"/api/meters/{meter_id}")

    response = client.get("/api/advance-payments/")
    assert response.status_code == 200
    assert response.json() == []


def test_wastewater_advance_payments_cascade_on_cold_meter_delete(client):
    """Deleting a water_cold meter must cascade delete its wastewater payments."""
    cold_meter_id = _create_meter(client, "water_cold")

    payment_data = {
        "category": "wastewater",
        "water_cold_meter_id": cold_meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "80.00"
    }

    client.post("/api/advance-payments/", json=payment_data)

    client.delete(f"/api/meters/{cold_meter_id}")

    response = client.get("/api/advance-payments/")
    assert response.status_code == 200
    assert response.json() == []


def test_same_meter_different_categories_no_overlap_conflict(client):
    """Same meter, different categories should not conflict (different category)."""
    meter_id = _create_meter(client, "gas")
    _create_meter(client, "electricity_import")  # meter_id = 2 for power_import
    # Create a second meter for power_import
    electricity_meter_id = _create_meter(client, "electricity_import")

    payment_gas = {
        "category": "gas",
        "meter_id": meter_id,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "120.00"
    }

    payment_power = {
        "category": "power_import",
        "meter_id": electricity_meter_id,
        "valid_from": "2024-06-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "200.00"
    }

    # Different categories, different meters - should be fine
    response1 = client.post("/api/advance-payments/", json=payment_gas)
    assert response1.status_code == 200

    response2 = client.post("/api/advance-payments/", json=payment_power)
    assert response2.status_code == 200