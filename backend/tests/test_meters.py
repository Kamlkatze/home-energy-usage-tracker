"""
Tests for meter-related API endpoints.
"""


def test_create_meter(client, sample_meter_data):
    """Test creating a new meter."""
    response = client.post("/api/meters/", json=sample_meter_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == 1
    assert data["meter_type"] == sample_meter_data["meter_type"]
    assert data["label"] == sample_meter_data["label"]
    assert data["unit"] == sample_meter_data["unit"]
    assert "created_at" in data


def test_create_meter_invalid_type(client):
    """Test creating meter with invalid meter_type."""
    invalid_data = {
        "meter_type": "invalid_type",
        "label": "Test Meter",
        "unit": "kWh"
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
        "unit": "m³"
    }
    
    response = client.put(f"/api/meters/{meter_id}", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == update_data["label"]
    assert data["unit"] == update_data["unit"]
    # meter_type should remain unchanged
    assert data["meter_type"] == sample_meter_data["meter_type"]


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


def test_create_meter_all_types(client):
    """Test creating meters for all meter types."""
    meter_types = ["electricity", "gas", "water"]
    
    for meter_type in meter_types:
        meter_data = {
            "meter_type": meter_type,
            "label": f"{meter_type.capitalize()} Meter",
            "unit": "kWh" if meter_type == "electricity" else "m³"
        }
        
        response = client.post("/api/meters/", json=meter_data)
        assert response.status_code == 200
        data = response.json()
        assert data["meter_type"] == meter_type