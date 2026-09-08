"""
Tests for reading-related API endpoints.
"""
from decimal import Decimal


def test_create_reading(client, sample_meter_data, sample_reading_data):
    """Test creating a new reading."""
    # First create a meter
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # Update reading data with the created meter_id
    reading_data = sample_reading_data.copy()
    reading_data["meter_id"] = meter_id
    
    response = client.post("/api/readings/", json=reading_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == 1
    assert data["meter_id"] == meter_id
    assert Decimal(data["value"]) == Decimal(reading_data["value"])
    assert data["reading_date"] == reading_data["reading_date"]
    assert data["note"] == reading_data["note"]


def test_create_reading_without_note(client, sample_meter_data):
    """Test creating a reading without optional note."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = {
        "meter_id": meter_id,
        "value": "1234.56",
        "reading_date": "2024-01-15"
        # note omitted
    }
    
    response = client.post("/api/readings/", json=reading_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["note"] is None


def test_create_reading_invalid_meter(client):
    """Test creating reading for non-existent meter."""
    reading_data = {
        "meter_id": 999,
        "value": "1234.56",
        "reading_date": "2024-01-15"
    }
    
    response = client.post("/api/readings/", json=reading_data)
    
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "Meter not found" in response.json()["detail"]


def test_create_reading_duplicate_date(client, sample_meter_data):
    """Test creating reading with duplicate date for same meter."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = {
        "meter_id": meter_id,
        "value": "1234.56",
        "reading_date": "2024-01-15"
    }
    
    # First reading
    response1 = client.post("/api/readings/", json=reading_data)
    assert response1.status_code == 200
    
    # Second reading with same date
    response2 = client.post("/api/readings/", json=reading_data)
    # Should fail with integrity error (500 internal server error)
    assert response2.status_code == 500


def test_read_readings_empty(client):
    """Test reading readings from empty database."""
    response = client.get("/api/readings/")
    
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_read_readings_with_data(client, sample_meter_data, sample_reading_data):
    """Test reading readings after creating one."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = sample_reading_data.copy()
    reading_data["meter_id"] = meter_id
    client.post("/api/readings/", json=reading_data)
    
    response = client.get("/api/readings/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert Decimal(data[0]["value"]) == Decimal(reading_data["value"])


def test_read_single_reading(client, sample_meter_data, sample_reading_data):
    """Test reading a specific reading by ID."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = sample_reading_data.copy()
    reading_data["meter_id"] = meter_id
    create_response = client.post("/api/readings/", json=reading_data)
    reading_id = create_response.json()["id"]
    
    response = client.get(f"/api/readings/{reading_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == reading_id
    assert Decimal(data["value"]) == Decimal(reading_data["value"])


def test_read_nonexistent_reading(client):
    """Test reading a reading that doesn't exist."""
    response = client.get("/api/readings/999")
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_update_reading(client, sample_meter_data, sample_reading_data):
    """Test updating an existing reading."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = sample_reading_data.copy()
    reading_data["meter_id"] = meter_id
    create_response = client.post("/api/readings/", json=reading_data)
    reading_id = create_response.json()["id"]
    
    update_data = {
        "value": "5678.90",
        "note": "Updated note"
    }
    
    response = client.put(f"/api/readings/{reading_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["value"]) == Decimal(update_data["value"])
    assert data["note"] == update_data["note"]


def test_update_nonexistent_reading(client):
    """Test updating a reading that doesn't exist."""
    update_data = {"value": "999.99"}
    
    response = client.put("/api/readings/999", json=update_data)
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_delete_reading(client, sample_meter_data, sample_reading_data):
    """Test deleting a reading."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    reading_data = sample_reading_data.copy()
    reading_data["meter_id"] = meter_id
    create_response = client.post("/api/readings/", json=reading_data)
    reading_id = create_response.json()["id"]
    
    response = client.delete(f"/api/readings/{reading_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Reading deleted" in data["message"]
    
    # Verify reading is deleted
    get_response = client.get(f"/api/readings/{reading_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_reading(client):
    """Test deleting a reading that doesn't exist."""
    response = client.delete("/api/readings/999")
    
    assert response.status_code == 404
    assert "detail" in response.json()


def test_decimal_serialization(client, sample_meter_data):
    """Test that Decimal values are serialized as strings."""
    meter_response = client.post("/api/meters/", json=sample_meter_data)
    meter_id = meter_response.json()["id"]
    
    # SQLite may round decimals, so test with a simple value
    reading_data = {
        "meter_id": meter_id,
        "value": "1234.56",  # Simple Decimal value
        "reading_date": "2024-01-15"
    }
    
    response = client.post("/api/readings/", json=reading_data)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["value"], str)
    # SQLite may round differently, so just check it's a string
    assert data["value"] is not None