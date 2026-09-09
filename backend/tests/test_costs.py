"""
Tests for the cost calculation endpoint (GET /api/costs/).
"""
from decimal import Decimal


def _create_meter(client, meter_type="electricity_import"):
    """Create a meter via the API and return its id."""
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": "Cost Test Meter"}
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
    """Create a consumption tariff period via the API.

    base_fee_monthly=None omits the field so the tariff has no base fee.
    """
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


def _calculate(client, meter_id, from_, to):
    """Call the cost calculation endpoint (uses the 'from' query alias)."""
    return client.get(
        "/api/costs/",
        params={"meter_id": meter_id, "from": from_, "to": to},
    )


def test_calculate_costs_happy_path(client):
    """Full calculation with exact arithmetic.

    Readings 1000.000 (2024-01-10) and 1150.500 (2024-03-10):
      consumption     = 1150.500 - 1000.000              = 150.500 kWh
      days_in_range   = (2024-03-10 - 2024-01-10).days    = 60
      base_fee_total  = 12.50 * 60 / 30                  = 25.00
      total_cost      = 150.500 * 0.35490 + 25.00        = 78.41245 -> 78.41
    """
    meter_id = _create_meter(client)  # electricity_import -> unit kWh
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.35490",
        base_fee_monthly="12.50",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == meter_id
    assert data["from_date"] == "2024-01-10"
    assert data["to_date"] == "2024-03-10"
    assert data["unit"] == "kWh"
    assert Decimal(data["consumption"]) == Decimal("150.500")
    assert Decimal(data["price_per_unit"]) == Decimal("0.35490")
    assert Decimal(data["base_fee_total"]) == Decimal("25.00")
    assert Decimal(data["total_cost"]) == Decimal("78.41")


def test_calculate_costs_no_reading_at_or_after_from(client):
    """404 when the start reading (smallest reading_date >= from) is missing."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-05")

    response = _calculate(client, meter_id, "2024-02-01", "2024-03-01")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein Zählerstand im angegebenen Zeitraum gefunden."
    )


def test_calculate_costs_no_reading_at_or_before_to(client):
    """404 when the end reading (largest reading_date <= to) is missing."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-06-01")

    response = _calculate(client, meter_id, "2024-01-01", "2024-05-31")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein Zählerstand im angegebenen Zeitraum gefunden."
    )


def test_calculate_costs_no_tariff_covers_full_range(client):
    """404 when no consumption tariff period fully contains [from, to]."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    # Tariff starts after the requested range begins
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-06-01",
        valid_to=None,
        price_per_unit="0.35490",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein gültiger Tarif für diesen Zeitraum gefunden."
    )


def test_calculate_costs_range_spans_tariff_change(client):
    """404 when the range spans a tariff change (no single covering period).

    Splitting proportionally across periods is out of scope by design.
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-12-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-06-30",
        price_per_unit="0.35490",
    )
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-07-01",
        valid_to=None,
        price_per_unit="0.40000",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-12-10")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein gültiger Tarif für diesen Zeitraum gefunden."
    )


def test_calculate_costs_from_after_to(client):
    """422 when from > to."""
    meter_id = _create_meter(client)

    response = _calculate(client, meter_id, "2024-03-10", "2024-01-10")

    assert response.status_code == 422
    assert "Ungültiger Zeitraum" in response.json()["detail"]


def test_calculate_costs_negative_consumption(client):
    """422 when end reading < start reading (e.g. meter reset/rollover)."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "2000.000", "2024-01-10")
    _create_reading(client, meter_id, "1500.000", "2024-03-10")

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 422
    assert "negativ" in response.json()["detail"]


def test_calculate_costs_base_fee_prorated(client):
    """Base fee is prorated by days with a fixed 30-day month.

    Readings 100.000 (2024-05-01) and 100.000 (2024-05-11):
      days_in_range  = (2024-05-11 - 2024-05-01).days = 10
      base_fee_total = 10.00 * 10 / 30 = 3.3333... -> 3.33 (ROUND_HALF_UP)
      total_cost     = 0.000 * 0.30000 + 3.3333...     -> 3.33
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "100.000", "2024-05-01")
    _create_reading(client, meter_id, "100.000", "2024-05-11")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )

    response = _calculate(client, meter_id, "2024-05-01", "2024-05-11")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("0.000")
    assert Decimal(data["base_fee_total"]) == Decimal("3.33")
    assert Decimal(data["total_cost"]) == Decimal("3.33")


def test_calculate_costs_base_fee_null_treated_as_zero(client):
    """A missing base_fee_monthly is treated as 0.

    Readings 100.000 (2024-01-10) and 110.000 (2024-01-20):
      days_in_range  = 10
      base_fee_total = 0.00
      total_cost     = 10.000 * 0.35490 = 3.549 -> 3.55
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "100.000", "2024-01-10")
    _create_reading(client, meter_id, "110.000", "2024-01-20")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.35490",
        base_fee_monthly=None,
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-01-20")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["base_fee_total"]) == Decimal("0.00")
    assert Decimal(data["total_cost"]) == Decimal("3.55")


def test_calculate_costs_query_parameter_alias(client):
    """The endpoint is exposed under query names 'meter_id', 'from', 'to'."""
    openapi = client.get("/api/openapi.json").json()
    params = openapi["paths"]["/api/costs/"]["get"]["parameters"]
    param_names = [p["name"] for p in params]

    assert sorted(param_names) == ["from", "meter_id", "to"]
