"""
Tests for the wastewater cost calculation endpoint
(GET /api/costs/wastewater/).

Wastewater is a derived value, not a real meter:
wastewater_consumption = max(0, cold-water consumption - garden-water
consumption), billed against a TariffPeriod with tariff_kind="wastewater"
attached to the cold-water meter's id.
"""
from decimal import Decimal


def _create_meter(client, meter_type):
    """Create a meter via the API and return its id."""
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": f"{meter_type} meter"}
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


def _create_wastewater_tariff(
    client, meter_id, valid_from, valid_to, price_per_unit, base_fee_monthly="6.00"
):
    """Create a wastewater tariff period via the API.

    base_fee_monthly=None omits the field so the tariff has no base fee.
    """
    payload = {
        "meter_id": meter_id,
        "tariff_kind": "wastewater",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "price_per_unit": price_per_unit,
    }
    if base_fee_monthly is not None:
        payload["base_fee_monthly"] = base_fee_monthly
    response = client.post("/api/tariffs/", json=payload)
    assert response.status_code == 200


def _calculate_wastewater(client, cold_meter_id, from_, to, garden_meter_id=None):
    """Call the wastewater cost endpoint (uses the 'from' query alias)."""
    params = {"water_cold_meter_id": cold_meter_id, "from": from_, "to": to}
    if garden_meter_id is not None:
        params["water_garden_meter_id"] = garden_meter_id
    return client.get("/api/costs/wastewater/", params=params)


def test_calculate_wastewater_costs_happy_path_both_meters(client):
    """Full calculation with both meters provided, exact arithmetic.

    Cold meter readings 1000.000 (2024-01-10) and 1150.500 (2024-03-10):
      cold_consumption = 1150.500 - 1000.000 = 150.500
    Garden meter readings 20.000 (2024-01-10) and 79.500 (2024-03-10):
      garden_consumption = 79.500 - 20.000  = 59.500
      wastewater         = 150.500 - 59.500 = 91.000
    days_in_range  = (2024-03-10 - 2024-01-10).days = 60
    base_fee_total = 6.00 * 60 / 30              = 12.00
    total_cost     = 91.000 * 2.10000 + 12.00    = 203.10
    """
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")
    _create_reading(client, cold_meter_id, "1000.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "1150.500", "2024-03-10")
    _create_reading(client, garden_meter_id, "20.000", "2024-01-10")
    _create_reading(client, garden_meter_id, "79.500", "2024-03-10")
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="2.10000",
        base_fee_monthly="6.00",
    )

    response = _calculate_wastewater(
        client, cold_meter_id, "2024-01-10", "2024-03-10", garden_meter_id
    )

    assert response.status_code == 200
    data = response.json()
    assert data["water_cold_meter_id"] == cold_meter_id
    assert data["water_garden_meter_id"] == garden_meter_id
    assert data["from_date"] == "2024-01-10"
    assert data["to_date"] == "2024-03-10"
    assert data["unit"] == "m³"
    assert Decimal(data["cold_consumption"]) == Decimal("150.500")
    assert Decimal(data["garden_consumption"]) == Decimal("59.500")
    assert Decimal(data["wastewater_consumption"]) == Decimal("91.000")
    assert Decimal(data["price_per_unit"]) == Decimal("2.10000")
    assert Decimal(data["base_fee_total"]) == Decimal("12.00")
    assert Decimal(data["total_cost"]) == Decimal("203.10")


def test_calculate_wastewater_costs_garden_meter_omitted(client):
    """Omitting water_garden_meter_id means garden_consumption = 0.

    The entire cold-water consumption counts as wastewater; no garden
    readings are required and water_garden_meter_id is null.
    """
    cold_meter_id = _create_meter(client, "water_cold")
    _create_reading(client, cold_meter_id, "1000.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "1150.500", "2024-03-10")
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="2.10000",
        base_fee_monthly="6.00",
    )

    response = _calculate_wastewater(client, cold_meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert data["water_garden_meter_id"] is None
    assert Decimal(data["garden_consumption"]) == Decimal(0)
    assert Decimal(data["wastewater_consumption"]) == Decimal("150.500")
    assert Decimal(data["total_cost"]) == Decimal("328.05")


def test_calculate_wastewater_costs_garden_exceeds_cold_floored_at_zero(client):
    """Garden consumption above cold consumption is floored at 0, no error.

    Cold 100.000 -> 200.000 (consumption 100.000),
    garden 50.000 -> 200.000 (consumption 150.000):
      wastewater = max(0, 100.000 - 150.000) = 0.000
    Only the prorated base fee remains:
      base_fee_total = 6.00 * 60 / 30 = 12.00, total_cost = 12.00
    """
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")
    _create_reading(client, cold_meter_id, "100.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "200.000", "2024-03-10")
    _create_reading(client, garden_meter_id, "50.000", "2024-01-10")
    _create_reading(client, garden_meter_id, "200.000", "2024-03-10")
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="2.10000",
        base_fee_monthly="6.00",
    )

    response = _calculate_wastewater(
        client, cold_meter_id, "2024-01-10", "2024-03-10", garden_meter_id
    )

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["wastewater_consumption"]) == Decimal("0.000")
    assert Decimal(data["base_fee_total"]) == Decimal("12.00")
    assert Decimal(data["total_cost"]) == Decimal("12.00")


def test_calculate_wastewater_costs_garden_meter_without_readings_is_404(client):
    """404 when water_garden_meter_id is provided but has no readings.

    Providing the parameter claims the meter is relevant, so the same
    reading-lookup rule as for the cold meter applies. This is distinct
    from omitting the parameter entirely (= 0 fallback, returns 200).
    """
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")
    _create_reading(client, cold_meter_id, "1000.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "1150.500", "2024-03-10")
    # Garden meter exists but has no readings in the requested range
    _create_reading(client, garden_meter_id, "20.000", "2025-01-10")
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="2.10000",
    )

    response = _calculate_wastewater(
        client, cold_meter_id, "2024-01-10", "2024-03-10", garden_meter_id
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein Zählerstand im angegebenen Zeitraum gefunden."
    )


def test_calculate_wastewater_costs_no_wastewater_tariff_covers_range(client):
    """404 when no wastewater tariff period fully contains [from, to].

    A consumption tariff on the cold meter does not count; the tariff
    must have tariff_kind="wastewater".
    """
    cold_meter_id = _create_meter(client, "water_cold")
    _create_reading(client, cold_meter_id, "1000.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "1150.500", "2024-03-10")
    # Only a wastewater tariff AFTER the range (and an unrelated
    # consumption tariff within it) exists.
    client.post(
        "/api/tariffs/",
        json={
            "meter_id": cold_meter_id,
            "tariff_kind": "consumption",
            "valid_from": "2024-01-01",
            "valid_to": "2024-12-31",
            "price_per_unit": "0.30000",
        },
    )
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-06-01",
        valid_to=None,
        price_per_unit="2.10000",
    )

    response = _calculate_wastewater(client, cold_meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Kein gültiger Tarif für diesen Zeitraum gefunden."
    )


def test_calculate_wastewater_costs_from_after_to(client):
    """422 when from > to."""
    cold_meter_id = _create_meter(client, "water_cold")

    response = _calculate_wastewater(client, cold_meter_id, "2024-03-10", "2024-01-10")

    assert response.status_code == 422
    assert "Ungültiger Zeitraum" in response.json()["detail"]


def test_calculate_wastewater_costs_negative_cold_consumption(client):
    """422 when the cold meter's consumption is negative (rollover).

    Same rule as the plain cost endpoint; a garden consumption above the
    cold consumption is NOT an error (floored at 0 instead).
    """
    cold_meter_id = _create_meter(client, "water_cold")
    _create_reading(client, cold_meter_id, "2000.000", "2024-01-10")
    _create_reading(client, cold_meter_id, "1500.000", "2024-03-10")
    _create_wastewater_tariff(
        client,
        cold_meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="2.10000",
    )

    response = _calculate_wastewater(client, cold_meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 422
    assert "negativ" in response.json()["detail"]


def test_calculate_wastewater_costs_query_parameter_alias(client):
    """The endpoint is exposed under query names 'water_cold_meter_id',
    'water_garden_meter_id', 'from' and 'to'."""
    openapi = client.get("/api/openapi.json").json()
    params = openapi["paths"]["/api/costs/wastewater/"]["get"]["parameters"]
    param_names = [p["name"] for p in params]

    assert sorted(param_names) == [
        "from",
        "to",
        "water_cold_meter_id",
        "water_garden_meter_id",
    ]
