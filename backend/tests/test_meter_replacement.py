"""
Tests for meter replacement (replaces_meter_id) feature.

Covers:
- Schema/API: replaces_meter_id in create/update/response
- Validation: self-reference rejection, meter_type mismatch rejection
- Cost calculation: chained consumption across 2 meters
- Cost calculation: normal (non-chained) meter remains unchanged
"""
from decimal import Decimal

# ---------------------------------------------------------------------------
# Helper functions (mirror style from existing test files)
# ---------------------------------------------------------------------------

def _create_meter(client, meter_type="electricity_import", label="Test Meter", replaces_meter_id=None):
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


def _create_tariff(client, meter_id, valid_from, valid_to, price_per_unit,
                   base_fee_monthly=None, gas_z_zahl=None, gas_brennwert=None):
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
    assert response.status_code == 200, response.text


def _calculate(client, meter_id, from_, to):
    return client.get(
        "/api/costs/",
        params={"meter_id": meter_id, "from": from_, "to": to},
    )


# ---------------------------------------------------------------------------
# Schema / API round-trip tests
# ---------------------------------------------------------------------------

def test_create_meter_with_replaces_meter_id_in_response(client):
    """replaces_meter_id is null for a standalone meter."""
    response = client.post(
        "/api/meters/",
        json={"meter_type": "electricity_import", "label": "Hauptzähler"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["replaces_meter_id"] is None


def test_create_replacement_meter_sets_replaces_meter_id(client):
    """Creating a meter with replaces_meter_id stores and returns it."""
    old_id = _create_meter(client, label="Alter Zähler")
    response = client.post(
        "/api/meters/",
        json={
            "meter_type": "electricity_import",
            "label": "Neuer Zähler",
            "replaces_meter_id": old_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["replaces_meter_id"] == old_id


def test_get_meter_returns_replaces_meter_id(client):
    """GET /api/meters/{id} includes replaces_meter_id."""
    old_id = _create_meter(client, label="Alt")
    new_id = _create_meter(client, label="Neu", replaces_meter_id=old_id)

    response = client.get(f"/api/meters/{new_id}")
    assert response.status_code == 200
    assert response.json()["replaces_meter_id"] == old_id


def test_update_meter_sets_replaces_meter_id(client):
    """PUT /api/meters/{id} can set replaces_meter_id after creation."""
    old_id = _create_meter(client, label="Alt")
    new_id = _create_meter(client, label="Neu")

    response = client.put(
        f"/api/meters/{new_id}",
        json={"replaces_meter_id": old_id},
    )
    assert response.status_code == 200
    assert response.json()["replaces_meter_id"] == old_id


def test_update_meter_can_clear_replaces_meter_id(client):
    """PUT /api/meters/{id} can clear replaces_meter_id by setting it to null."""
    old_id = _create_meter(client, label="Alt")
    new_id = _create_meter(client, label="Neu", replaces_meter_id=old_id)

    response = client.put(
        f"/api/meters/{new_id}",
        json={"replaces_meter_id": None},
    )
    assert response.status_code == 200
    assert response.json()["replaces_meter_id"] is None


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_create_meter_self_reference_rejected(client):
    """422 when a meter tries to reference itself during creation is not possible
    (we don't know the id before creation), but setting it via update is caught."""
    meter_id = _create_meter(client, label="Zähler A")

    response = client.put(
        f"/api/meters/{meter_id}",
        json={"replaces_meter_id": meter_id},
    )
    assert response.status_code == 422
    assert "selbst" in response.json()["detail"].lower() or "selbst" in response.json()["detail"]


def test_create_meter_replaces_nonexistent_rejected(client):
    """422 when replaces_meter_id references a non-existent meter."""
    response = client.post(
        "/api/meters/",
        json={
            "meter_type": "electricity_import",
            "label": "Neuer Zähler",
            "replaces_meter_id": 99999,
        },
    )
    assert response.status_code == 422
    assert "99999" in response.json()["detail"]


def test_create_meter_replaces_different_type_rejected(client):
    """422 when replaces_meter_id references a meter of a different type.

    A gas meter cannot replace an electricity meter.
    """
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom")

    response = client.post(
        "/api/meters/",
        json={
            "meter_type": "gas",
            "label": "Gas",
            "replaces_meter_id": elec_id,
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "electricity_import" in detail or "gas" in detail


def test_update_meter_replaces_different_type_rejected(client):
    """422 when updating replaces_meter_id to a meter of a different type."""
    gas_id = _create_meter(client, meter_type="gas", label="Gas")
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom Neu")

    response = client.put(
        f"/api/meters/{elec_id}",
        json={"replaces_meter_id": gas_id},
    )
    assert response.status_code == 422


def test_update_meter_type_mismatch_after_type_change_rejected(client):
    """422 when changing meter_type would make the existing replaces_meter_id invalid."""
    old_elec = _create_meter(client, meter_type="electricity_import", label="Alt Strom")
    new_elec = _create_meter(client, meter_type="electricity_import", label="Neu Strom",
                              replaces_meter_id=old_elec)

    # Changing new_elec to gas would conflict with old_elec (electricity)
    response = client.put(
        f"/api/meters/{new_elec}",
        json={"meter_type": "gas"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Cost calculation: normal (non-chained) meter is unchanged
# ---------------------------------------------------------------------------

def test_normal_meter_cost_unchanged(client):
    """A meter with no replacement chain uses the original calculation logic.

    Readings 1000.000 (2024-01-10) and 1150.500 (2024-03-10):
      consumption     = 150.500 kWh
      days_in_range   = 60
      base_fee_total  = 12.50 * 60 / 30 = 25.00
      total_cost      = 150.500 * 0.35490 + 25.00 = 78.41
    """
    meter_id = _create_meter(client, label="Standalone")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    _create_tariff(
        client, meter_id,
        valid_from="2024-01-01", valid_to="2024-12-31",
        price_per_unit="0.35490", base_fee_monthly="12.50",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("150.500")
    assert Decimal(data["base_fee_total"]) == Decimal("25.00")
    assert Decimal(data["total_cost"]) == Decimal("78.41")


# ---------------------------------------------------------------------------
# Cost calculation: chained consumption across 2 meters
# ---------------------------------------------------------------------------

def test_chained_meter_consumption(client):
    """Cost calculation follows the replacement chain.

    Setup:
      Old meter P: readings 1000.000 (2024-01-01) and 1300.000 (2024-03-31)
        → 300 kWh over 90 days (Jan 1 – Mar 31)
      New meter M (replaces P): readings 0.000 (2024-04-01) and 200.000 (2024-06-30)
        → 200 kWh over 90 days (Apr 1 – Jun 30)

    Request: meter_id = M.id, from=2024-01-01, to=2024-06-30
    Expected total consumption = 300 + 200 = 500 kWh

    Tariffs:
      P: 2024-01-01 to 2024-12-31, 0.30000 €/kWh, base_fee_monthly=10.00
      M: 2024-01-01 to 2024-12-31, 0.40000 €/kWh, base_fee_monthly=10.00

    Segment P: 2024-01-01 to 2024-03-31 (90 days inclusive-exclusive)
      consumption = 300 kWh
      base fee: 10.00 * 90/30 = 30.00
      energy: 300 * 0.30000 = 90.00
    Segment M: 2024-04-01 to 2024-06-30 (90 days inclusive-exclusive)
      consumption = 200 kWh
      base fee: 10.00 * 90/30 = 30.00
      energy: 200 * 0.40000 = 80.00

    Total:
      base_fee_total = 60.00
      total_cost = 60.00 + 90.00 + 80.00 = 230.00
    """
    old_id = _create_meter(client, label="Alter Zähler P")
    new_id = _create_meter(client, label="Neuer Zähler M", replaces_meter_id=old_id)

    # Old meter readings
    _create_reading(client, old_id, "1000.000", "2024-01-01")
    _create_reading(client, old_id, "1300.000", "2024-03-31")

    # New meter readings (starts at 0)
    _create_reading(client, new_id, "0.000", "2024-04-01")
    _create_reading(client, new_id, "200.000", "2024-06-30")

    # Tariffs on each meter
    _create_tariff(client, old_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000", base_fee_monthly="10.00")
    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.40000", base_fee_monthly="10.00")

    # Query via the NEW meter id
    response = _calculate(client, new_id, "2024-01-01", "2024-06-30")

    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == new_id
    assert Decimal(data["consumption"]) == Decimal(500)
    assert Decimal(data["base_fee_total"]) == Decimal("60.00")
    assert Decimal(data["total_cost"]) == Decimal("230.00")


def test_chained_meter_with_tariff_change_in_chain(client):
    """Chain consumption with a tariff change mid-way through one meter's segment.

    Setup:
      Old meter P: readings 500.000 (2024-01-01) and 700.000 (2024-03-31) → 200 kWh (90 days)
      New meter M (replaces P): readings 0.000 (2024-04-01) and 300.000 (2024-09-28) → 300 kWh
        (2024-04-01 to 2024-09-28 = 180 days)

    Tariffs on P:
      Period 1: 2024-01-01 to 2024-01-31 (31 days overlap with P's segment 2024-01-01 to 2024-03-30)
        price=0.20000, no base fee
      Period 2: 2024-02-01 onwards
        price=0.25000, no base fee

    Tariffs on M:
      Single: 2024-04-01 onwards, price=0.35000, no base fee

    P segment: 2024-01-01 to 2024-03-31 (90 days inclusive-exclusive range)
      Total consumption = 200 kWh
      Period 1 overlap: 2024-01-01 to 2024-01-31 = 31 days
        share: 200 * 31/90 = 68.888... kWh * 0.20 = 13.777...
      Period 2 overlap: 2024-02-01 to 2024-03-31 = 59 days
        share: 200 * 59/90 = 131.111... kWh * 0.25 = 32.777...
      P energy raw = 46.555...

    M segment: 2024-04-01 to 2024-09-28 (180 days inclusive-exclusive)
      Total consumption = 300 kWh, price = 0.35000
      M energy raw = 300 * 0.35000 = 105.000

    Total base_fee = 0.00
    Total energy = 46.555... + 105.000 = 151.555... → 151.56
    total_cost = 151.56
    """
    old_id = _create_meter(client, label="Zähler P alt")
    new_id = _create_meter(client, label="Zähler M neu", replaces_meter_id=old_id)

    _create_reading(client, old_id, "500.000", "2024-01-01")
    _create_reading(client, old_id, "700.000", "2024-03-31")

    _create_reading(client, new_id, "0.000", "2024-04-01")
    _create_reading(client, new_id, "300.000", "2024-09-28")

    # Tariffs on old meter (two periods)
    _create_tariff(client, old_id, valid_from="2024-01-01", valid_to="2024-01-31",
                   price_per_unit="0.20000")
    _create_tariff(client, old_id, valid_from="2024-02-01", valid_to=None,
                   price_per_unit="0.25000")

    # Tariff on new meter
    _create_tariff(client, new_id, valid_from="2024-04-01", valid_to=None,
                   price_per_unit="0.35000")

    response = _calculate(client, new_id, "2024-01-01", "2024-09-28")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal(500)
    assert Decimal(data["base_fee_total"]) == Decimal("0.00")
    # P segment energy: 200 * 31/90 * 0.20 + 200 * 59/90 * 0.25 = 46.5555...
    # M segment energy: 300 * 0.35 = 105
    # Total = 151.555... -> 151.56
    assert Decimal(data["total_cost"]) == Decimal("151.56")


def test_chained_meter_404_when_no_readings_anywhere(client):
    """404 when the chain has no readings at all in the requested range."""
    old_id = _create_meter(client, label="Leer alt")
    new_id = _create_meter(client, label="Leer neu", replaces_meter_id=old_id)

    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")

    response = _calculate(client, new_id, "2024-01-01", "2024-12-31")

    assert response.status_code == 404


def test_chained_meter_no_negative_consumption(client):
    """Chain calculation avoids negative consumption from a counter reset.

    Old meter ends at 9999, new meter starts at 0.
    Without chain awareness: 0 - 9999 = -9999 (wrong).
    With chain awareness: (9999 - 8000) + (500 - 0) = 1999 + 500 = 2499.
    """
    old_id = _create_meter(client, label="Counter reset alt")
    new_id = _create_meter(client, label="Counter reset neu", replaces_meter_id=old_id)

    _create_reading(client, old_id, "8000.000", "2024-01-01")
    _create_reading(client, old_id, "9999.000", "2024-03-31")

    _create_reading(client, new_id, "0.000", "2024-04-01")
    _create_reading(client, new_id, "500.000", "2024-06-30")

    _create_tariff(client, old_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")
    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")

    response = _calculate(client, new_id, "2024-01-01", "2024-06-30")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal(2499)
    # total cost: (1999 + 500) * 0.30 = 2499 * 0.30 = 749.70
    assert Decimal(data["total_cost"]) == Decimal("749.70")


def test_chained_meter_only_new_meter_has_readings_in_range(client):
    """When the requested range falls entirely within the new meter's lifetime,
    only the new meter's readings are used (old meter is irrelevant for this range).
    """
    old_id = _create_meter(client, label="Vorgänger")
    new_id = _create_meter(client, label="Nachfolger", replaces_meter_id=old_id)

    # Old meter has readings in 2023 (outside range)
    _create_reading(client, old_id, "5000.000", "2023-01-01")
    _create_reading(client, old_id, "5500.000", "2023-12-31")

    # New meter starts in 2024
    _create_reading(client, new_id, "0.000", "2024-01-01")
    _create_reading(client, new_id, "400.000", "2024-06-30")

    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.40000")

    # Query only in 2024 (entirely in new meter's range)
    response = _calculate(client, new_id, "2024-01-01", "2024-06-30")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal(400)
    assert Decimal(data["total_cost"]) == Decimal("160.00")


def test_list_meters_includes_replaces_meter_id(client):
    """GET /api/meters/ returns replaces_meter_id for all meters."""
    old_id = _create_meter(client, label="Old")
    new_id = _create_meter(client, label="New", replaces_meter_id=old_id)

    response = client.get("/api/meters/")
    assert response.status_code == 200
    meters = {m["id"]: m for m in response.json()}

    assert meters[old_id]["replaces_meter_id"] is None
    assert meters[new_id]["replaces_meter_id"] == old_id
