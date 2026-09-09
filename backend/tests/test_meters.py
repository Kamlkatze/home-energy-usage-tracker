"""
Tests for meter-related API endpoints.
"""

import pytest

from app.models.meter import METER_TYPE_UNITS, MeterType


def test_create_meter(client, sample_meter_data):
    """Test creating a new meter."""
    response = client.post("/api/meters/", json=sample_meter_data)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == 1
    assert data["meter_type"] == sample_meter_data["meter_type"]
    assert data["label"] == sample_meter_data["label"]
    # The unit is derived server-side from meter_type, never from client input
    assert data["unit"] == METER_TYPE_UNITS[MeterType.GAS]
    assert "created_at" in data


def test_create_meter_invalid_type(client):
    """Test creating meter with invalid meter_type."""
    invalid_data = {
        "meter_type": "invalid_type",
        "label": "Test Meter",
    }

    response = client.post("/api/meters/", json=invalid_data)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_read_meters_empty(client):
    """Test reading meters from empty database."""
    response = client.get("/api/meters/")

    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_read_meters_with_data(client, sample_meter_data):
    """Test reading meters after creating one."""
    client.post("/api/meters/", json=sample_meter_data)

    response = client.get("/api/meters/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["meter_type"] == sample_meter_data["meter_type"]


def test_read_meters_pagination(client, sample_meter_data):
    """Test reading meters with pagination."""
    for i in range(5):
        meter_data = sample_meter_data.copy()
        meter_data["label"] = f"Meter {i+1}"
        client.post("/api/meters/", json=meter_data)

    response = client.get("/api/meters/?skip=2&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_read_single_meter(client, sample_meter_data):
    """Test reading a specific meter by ID."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    response = client.get(f"/api/meters/{meter_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == meter_id
    assert data["label"] == sample_meter_data["label"]


def test_read_nonexistent_meter(client):
    """Test reading a meter that doesn't exist."""
    response = client.get("/api/meters/999")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_update_meter(client, sample_meter_data):
    """Test updating an existing meter."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    update_data = {
        "label": "Updated Meter Label",
    }

    response = client.put(f"/api/meters/{meter_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    # unit is server-derived and must not change when only the label is updated
    assert data["unit"] == METER_TYPE_UNITS[MeterType.GAS]
    # meter_type should remain unchanged
    assert data["meter_type"] == sample_meter_data["meter_type"]


def test_update_meter_type_rederives_unit(client, sample_meter_data):
    """Test that changing meter_type re-derives the unit server-side."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    response = client.put(
        f"/api/meters/{meter_id}", json={"meter_type": "electricity_import"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meter_type"] == "electricity_import"
    assert data["unit"] == METER_TYPE_UNITS[MeterType.ELECTRICITY_IMPORT]


def test_update_nonexistent_meter(client):
    """Test updating a meter that doesn't exist."""
    update_data = {"label": "Updated"}

    response = client.put("/api/meters/999", json=update_data)

    assert response.status_code == 404
    assert "detail" in response.json()


def test_delete_meter(client, sample_meter_data):
    """Test deleting a meter."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    response = client.delete(f"/api/meters/{meter_id}")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Meter deleted" in data["message"]

    # Verify meter is deleted
    get_response = client.get(f"/api/meters/{meter_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_meter(client):
    """Test deleting a meter that doesn't exist."""
    response = client.delete("/api/meters/999")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_read_meter_readings_empty(client, sample_meter_data):
    """Test reading readings for a meter with no readings."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    response = client.get(f"/api/meters/{meter_id}/readings")

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.parametrize(
    ("meter_type", "expected_unit"),
    [
        ("gas", "m³"),
        ("water_cold", "m³"),
        ("water_garden", "m³"),
        ("electricity_import", "kWh"),
        ("electricity_export", "kWh"),
        ("electricity_production", "kWh"),
    ],
)
def test_create_meter_all_types_derive_unit(client, meter_type, expected_unit):
    """Test creating meters for all 6 meter types derives the correct unit."""
    meter_data = {
        "meter_type": meter_type,
        "label": f"{meter_type} Meter",
    }

    response = client.post("/api/meters/", json=meter_data)
    assert response.status_code == 200
    data = response.json()
    assert data["meter_type"] == meter_type
    assert data["unit"] == expected_unit


def test_create_meter_with_unit_rejected(client, sample_meter_data):
    """Test that a client-supplied unit field is rejected with 422 on create."""
    payload = {**sample_meter_data, "unit": "custom_unit"}

    response = client.post("/api/meters/", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error.get("loc") == ["body", "unit"] for error in errors)


def test_update_meter_with_unit_rejected(client, sample_meter_data):
    """Test that a client-supplied unit field is rejected with 422 on update."""
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]

    response = client.put(f"/api/meters/{meter_id}", json={"unit": "kWh"})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error.get("loc") == ["body", "unit"] for error in errors)


def test_read_meter_types(client):
    """Test GET /api/meters/types returns all 6 types in declaration order."""
    response = client.get("/api/meters/types")

    assert response.status_code == 200
    assert response.json() == [
        {"value": "gas", "label": "Gas", "unit": "m³"},
        {"value": "water_cold", "label": "Kaltwasser", "unit": "m³"},
        {"value": "water_garden", "label": "Gartenwasser", "unit": "m³"},
        {"value": "electricity_import", "label": "Strom Bezug", "unit": "kWh"},
        {"value": "electricity_export", "label": "Strom Einspeisung", "unit": "kWh"},
        {
            "value": "electricity_production",
            "label": "Strom Erzeugung",
            "unit": "kWh",
        },
    ]


def test_create_meter_without_meter_number(client, sample_meter_data):
    """Test creating a meter without meter_number (value should be null)."""
    # Ensure meter_number is not in the sample data
    assert "meter_number" not in sample_meter_data
    
    response = client.post("/api/meters/", json=sample_meter_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == 1
    assert data["meter_type"] == sample_meter_data["meter_type"]
    assert data["label"] == sample_meter_data["label"]
    assert "meter_number" in data
    assert data["meter_number"] is None
    assert "created_at" in data


def test_create_meter_with_meter_number(client):
    """Test creating a meter with meter_number set."""
    meter_data = {
        "meter_type": "electricity_import",
        "label": "Main Electricity Meter",
        "meter_number": "1EMH0012345678"
    }
    
    response = client.post("/api/meters/", json=meter_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["meter_type"] == "electricity_import"
    assert data["label"] == "Main Electricity Meter"
    assert data["meter_number"] == "1EMH0012345678"
    assert data["unit"] == "kWh"


def test_update_meter_number(client, sample_meter_data):
    """Test updating meter_number on an existing meter."""
    # Create meter without meter_number
    create_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = create_response.json()["id"]
    
    # Update meter_number
    update_data = {"meter_number": "1EMH0098765432"}
    response = client.put(f"/api/meters/{meter_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["meter_number"] == "1EMH0098765432"
    assert data["label"] == sample_meter_data["label"]  # unchanged
    assert data["meter_type"] == sample_meter_data["meter_type"]  # unchanged
    
    # Verify via GET
    get_response = client.get(f"/api/meters/{meter_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["meter_number"] == "1EMH0098765432"


def test_update_meter_number_to_null(client):
    """Test updating meter_number to null (clearing it)."""
    # Create meter with meter_number
    meter_data = {
        "meter_type": "gas",
        "label": "Test Meter",
        "meter_number": "1EMH0012345678"
    }
    create_response = client.post("/api/meters/", json=meter_data)
    meter_id = create_response.json()["id"]
    
    # Update meter_number to null
    update_data = {"meter_number": None}
    response = client.put(f"/api/meters/{meter_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["meter_number"] is None
    
    # Verify via GET
    get_response = client.get(f"/api/meters/{meter_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["meter_number"] is None
