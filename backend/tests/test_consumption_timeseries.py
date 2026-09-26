"""
Tests for the consumption-timeseries endpoint
(GET /api/costs/consumption-timeseries).

Covers:
- Single meter, multiple readings in range, correct deltas
- First reading in range has a previous reading before "from" → delta
  calculated correctly using that out-of-range reading
- First reading in range has NO previous reading → consumption and
  cost null
- Replacement chain: delta correctly spans chain boundary
- No tariff available for a sub-period → cost null, consumption present
- Meter/chain with zero readings in range → omitted from response
- Gas meter: m³→kWh conversion applied correctly in cost
- Invalid range (from > to) → 422
- Empty database → empty list
"""
from decimal import Decimal


def _create_meter(client, meter_type="electricity_import", label="Test Meter",
                  replaces_meter_id=None):
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


def _get_timeseries(client, from_, to, meter_type=None):
    params = {"from": from_, "to": to}
    if meter_type is not None:
        params["meter_type"] = meter_type
    return client.get(
        "/api/costs/consumption-timeseries",
        params=params,
    )


def test_multiple_readings_correct_deltas(client):
    """Single meter, multiple readings in range — consumption and cost deltas
    between consecutive readings."""
    meter_id = _create_meter(client, label="Strom")
    _create_reading(client, meter_id, "1000.000", "2024-01-01")
    _create_reading(client, meter_id, "1100.000", "2024-02-01")
    _create_reading(client, meter_id, "1250.000", "2024-03-01")
    _create_tariff(client, meter_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000", base_fee_monthly="10.00")

    response = _get_timeseries(client, "2024-01-15", "2024-03-15")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["meter_id"] == meter_id
    points = entry["points"]

    # The reading on 2024-02-01 is the first in range (2024-01-01 is before
    # from). Its previous reading (2024-01-01, value=1000) is before "from",
    # so the delta is 1100 - 1000 = 100.
    assert len(points) == 2
    assert points[0]["date"] == "2024-02-01"
    assert points[0]["value"] == "1100.000"
    assert Decimal(points[0]["consumption_since_previous"]) == Decimal("100.000")
    assert points[0]["cost_since_previous"] is not None

    # The reading on 2024-03-01: previous in-range reading is 2024-02-01,
    # delta = 1250 - 1100 = 150.
    assert points[1]["date"] == "2024-03-01"
    assert points[1]["value"] == "1250.000"
    assert Decimal(points[1]["consumption_since_previous"]) == Decimal("150.000")
    assert points[1]["cost_since_previous"] is not None


def test_first_reading_has_previous_before_from(client):
    """First reading in range → previous reading before 'from' is used for
    delta."""
    meter_id = _create_meter(client, label="Strom")
    _create_reading(client, meter_id, "500.000", "2024-01-01")
    _create_reading(client, meter_id, "600.000", "2024-06-01")
    _create_reading(client, meter_id, "800.000", "2024-12-01")
    _create_tariff(client, meter_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")

    response = _get_timeseries(client, "2024-02-01", "2024-07-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    points = data[0]["points"]

    # 2024-06-01 is first in range; prev = 2024-01-01 (value=500).
    assert len(points) == 1
    assert points[0]["date"] == "2024-06-01"
    assert Decimal(points[0]["consumption_since_previous"]) == Decimal("100.000")


def test_first_reading_no_previous(client):
    """First reading in range has NO previous reading at all → both fields
    null."""
    meter_id = _create_meter(client, label="Ohne Vorgänger")
    _create_reading(client, meter_id, "500.000", "2024-06-01")
    _create_reading(client, meter_id, "600.000", "2024-12-01")
    _create_tariff(client, meter_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")

    response = _get_timeseries(client, "2024-02-01", "2024-07-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    points = data[0]["points"]

    assert len(points) == 1
    assert points[0]["date"] == "2024-06-01"
    assert points[0]["consumption_since_previous"] is None
    assert points[0]["cost_since_previous"] is None

    # 2024-12-01 is also in range → has previous (2024-06-01), delta = 100.
    response2 = _get_timeseries(client, "2024-02-01", "2025-01-01")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2) == 1
    points2 = data2[0]["points"]
    assert len(points2) == 2
    assert points2[0]["consumption_since_previous"] is None
    assert Decimal(points2[1]["consumption_since_previous"]) == Decimal("100.000")


def test_replacement_chain_cross_boundary(client):
    """Replacement chain: reading in successor has predecessor's reading as
    previous → delta correctly spans chain boundary."""
    old_id = _create_meter(client, label="Alt", meter_type="gas")
    new_id = _create_meter(client, label="Neu", meter_type="gas",
                           replaces_meter_id=old_id)

    # Predecessor readings.
    _create_reading(client, old_id, "0.000", "2023-12-31")
    _create_reading(client, old_id, "800.000", "2024-06-30")

    # Successor reading (counter continued: value 800 → carry-over).
    _create_reading(client, new_id, "800.000", "2024-07-01")
    _create_reading(client, new_id, "1100.000", "2024-12-31")

    _create_tariff(client, old_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.10000", base_fee_monthly=None,
                   gas_z_zahl="0.9612", gas_brennwert="11.482")
    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.10000", base_fee_monthly=None,
                   gas_z_zahl="0.9612", gas_brennwert="11.482")

    response = _get_timeseries(client, "2024-07-01", "2025-01-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["meter_id"] == new_id
    points = entry["points"]

    # Two readings: 2024-07-01 (800) and 2024-12-31 (1100).
    assert len(points) == 2

    # First point: value=800, prev = 800 on 2024-06-30 (predecessor).
    # Delta = 800 - 800 = 0.
    assert points[0]["date"] == "2024-07-01"
    assert points[0]["value"] == "800.000"
    assert Decimal(points[0]["consumption_since_previous"]) == Decimal("0.000")
    assert points[0]["cost_since_previous"] is not None

    # Second point: in-range prev = 2024-07-01 (800), delta = 1100 - 800 = 300.
    assert points[1]["date"] == "2024-12-31"
    assert Decimal(points[1]["consumption_since_previous"]) == Decimal("300.000")
    assert points[1]["cost_since_previous"] is not None


def test_no_tariff_cost_null(client):
    """No tariff available for a sub-period → cost_since_previous is null,
    consumption is still present."""
    meter_id = _create_meter(client, label="Kein Tarif")
    # Readings: 2024-01-01, 2024-03-15, 2024-06-01, 2024-12-01.
    _create_reading(client, meter_id, "1000.000", "2024-01-01")
    _create_reading(client, meter_id, "1100.000", "2024-03-15")
    _create_reading(client, meter_id, "1200.000", "2024-06-01")
    _create_reading(client, meter_id, "1300.000", "2024-12-01")

    # Tariff covers [2024-01-01, 2024-04-01].
    _create_tariff(client, meter_id, valid_from="2024-01-01",
                   valid_to="2024-04-01", price_per_unit="0.30000")

    response = _get_timeseries(client, "2024-01-01", "2025-01-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    points = data[0]["points"]

    assert len(points) == 4

    # Point 1 (2024-01-01): no previous → both null.
    assert points[0]["consumption_since_previous"] is None
    assert points[0]["cost_since_previous"] is None

    # Point 2 (2024-03-15): prev = 2024-01-01, delta = 100.
    # Sub-period [2024-01-01, 2024-03-15) is fully covered by tariff → cost.
    assert Decimal(points[1]["consumption_since_previous"]) == Decimal("100.000")
    assert points[1]["cost_since_previous"] is not None

    # Point 3 (2024-06-01): prev = 2024-03-15, delta = 100.
    # Sub-period [2024-03-15, 2024-06-01) extends beyond tariff end (2024-04-01)
    # → cost null (coverage check fails).
    assert Decimal(points[2]["consumption_since_previous"]) == Decimal("100.000")
    assert points[2]["cost_since_previous"] is None

    # Point 4 (2024-12-01): prev = 2024-06-01, delta = 100.
    # Sub-period [2024-06-01, 2024-12-01) is entirely outside tariff → cost null.
    assert Decimal(points[3]["consumption_since_previous"]) == Decimal("100.000")
    assert points[3]["cost_since_previous"] is None


def test_chain_no_readings_in_range_omitted(client):
    """Meter/chain with zero readings in range → omitted from response."""
    meter_id = _create_meter(client, label="Leer")
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1100.000", "2024-12-31")

    response = _get_timeseries(client, "2025-01-01", "2025-12-31")
    assert response.status_code == 200
    assert response.json() == []


def test_gas_conversion_in_cost(client):
    """Gas meter: m³→kWh conversion applied correctly in cost calculation."""
    meter_id = _create_meter(client, meter_type="gas", label="Gas")
    _create_reading(client, meter_id, "0.000", "2024-01-01")
    _create_reading(client, meter_id, "100.000", "2024-06-01")
    _create_tariff(client, meter_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.12000", base_fee_monthly=None,
                   gas_z_zahl="0.9500", gas_brennwert="11.500")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    points = data[0]["points"]

    # First point (2024-01-01): no previous → null.
    assert points[0]["consumption_since_previous"] is None
    assert points[0]["cost_since_previous"] is None

    # Second point (2024-06-01): delta = 100 m³, prev = 2024-01-01.
    # Cost should use m³→kWh conversion:
    #   kWh = 100 * 0.9500 * 11.500 = 1092.5 kWh
    #   cost = 1092.5 * 0.12 = 131.10
    assert Decimal(points[1]["consumption_since_previous"]) == Decimal("100.000")
    assert Decimal(points[1]["cost_since_previous"]) == Decimal("131.10")


def test_invalid_range_422(client):
    """from > to → 422."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-01")
    response = _get_timeseries(client, "2024-06-01", "2024-01-01")
    assert response.status_code == 422


def test_empty_database(client):
    """Empty database → empty list."""
    response = _get_timeseries(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    assert response.json() == []


def test_no_meter_type_filter_returns_all(client):
    """Without `meter_type`, meters of all types are returned (previous
    behaviour)."""
    gas_id = _create_meter(client, meter_type="gas", label="Gas")
    water_id = _create_meter(client, meter_type="water_cold", label="Wasser")
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom")
    for mid in (gas_id, water_id, elec_id):
        _create_reading(client, mid, "100.000", "2024-06-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31")
    assert response.status_code == 200
    data = response.json()
    assert {entry["meter_id"] for entry in data} == {gas_id, water_id, elec_id}


def test_meter_type_filter_gas(client):
    """Filtering by `meter_type=gas` returns only gas meters."""
    gas_id = _create_meter(client, meter_type="gas", label="Gas")
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom")
    for mid in (gas_id, elec_id):
        _create_reading(client, mid, "100.000", "2024-06-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31",
                               meter_type="gas")
    assert response.status_code == 200
    data = response.json()
    assert {entry["meter_id"] for entry in data} == {gas_id}


def test_meter_type_filter_water(client):
    """Filtering by `meter_type=water_cold` returns only water meters."""
    water_id = _create_meter(client, meter_type="water_cold", label="Wasser")
    garden_id = _create_meter(client, meter_type="water_garden", label="Garten")
    for mid in (water_id, garden_id):
        _create_reading(client, mid, "100.000", "2024-06-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31",
                               meter_type="water_cold")
    assert response.status_code == 200
    data = response.json()
    assert {entry["meter_id"] for entry in data} == {water_id}


def test_meter_type_filter_electricity(client):
    """Filtering by `meter_type=electricity_import` returns only electricity
    import meters."""
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom")
    export_id = _create_meter(client, meter_type="electricity_export", label="Einspeisung")
    for mid in (elec_id, export_id):
        _create_reading(client, mid, "100.000", "2024-06-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31",
                               meter_type="electricity_import")
    assert response.status_code == 200
    data = response.json()
    assert {entry["meter_id"] for entry in data} == {elec_id}


def test_meter_type_filter_no_match_returns_empty(client):
    """Filtering by a valid type with no matching meters → empty list."""
    elec_id = _create_meter(client, meter_type="electricity_import", label="Strom")
    _create_reading(client, elec_id, "100.000", "2024-06-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31",
                               meter_type="gas")
    assert response.status_code == 200
    assert response.json() == []


def test_invalid_meter_type_422(client):
    """Invalid `meter_type` value → 422 validation error."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-01")

    response = _get_timeseries(client, "2024-01-01", "2024-12-31",
                               meter_type="invalid_type")
    assert response.status_code == 422