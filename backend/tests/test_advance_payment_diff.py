"""
Tests for the advance payment diff endpoint (GET /api/costs/advance-payment-diff).
"""
from datetime import date
from decimal import Decimal

from app.api.costs import _compute_wastewater_consumption


def _create_meter(client, meter_type="electricity_import"):
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": "Diff Test Meter"}
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_reading(client, meter_id, value, reading_date):
    response = client.post(
        "/api/readings/",
        json={"meter_id": meter_id, "value": value, "reading_date": reading_date},
    )
    assert response.status_code == 200


def _create_tariff(
    client, meter_id, valid_from, valid_to, price_per_unit, base_fee_monthly="12.50",
    gas_z_zahl=None, gas_brennwert=None, tariff_kind="consumption",
):
    payload = {
        "meter_id": meter_id,
        "tariff_kind": tariff_kind,
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
    assert response.status_code == 200


def _create_advance_payment(client, meter_id, valid_from, valid_to, monthly_amount, category="power_import"):
    payload = {
        "category": category,
        "meter_id": meter_id,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "monthly_amount": monthly_amount,
    }
    response = client.post("/api/advance-payments/", json=payload)
    assert response.status_code == 200


def _create_wastewater_advance_payment(client, water_cold_meter_id, valid_from, valid_to, monthly_amount, water_garden_meter_id=None):
    payload = {
        "category": "wastewater",
        "water_cold_meter_id": water_cold_meter_id,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "monthly_amount": monthly_amount,
    }
    if water_garden_meter_id is not None:
        payload["water_garden_meter_id"] = water_garden_meter_id
    response = client.post("/api/advance-payments/", json=payload)
    assert response.status_code == 200


def call_diff(client, meter_id, year, as_of_date=None):
    params = {"meter_id": meter_id, "year": year}
    if as_of_date is not None:
        params["as_of_date"] = as_of_date
    return client.get("/api/costs/advance-payment-diff", params=params)


def call_diff_wastewater(client, water_cold_meter_id, year, as_of_date=None, water_garden_meter_id=None):
    params = {"meter_id": water_cold_meter_id, "year": year, "water_cold_meter_id": water_cold_meter_id}
    if water_garden_meter_id is not None:
        params["water_garden_meter_id"] = water_garden_meter_id
    if as_of_date is not None:
        params["as_of_date"] = as_of_date
    return client.get("/api/costs/advance-payment-diff", params=params)


def test_diff_completed_year_full_advance_payment(client):
    """Happy path: completed year (2023), single advance payment covering the full year.

    Advance payment: 100.00/month, valid 2023-01-01..2023-12-31
    Expected total: 12 * 100.00 = 1200.00

    Yearly cost (same setup as test_yearly_projection_completed_year):
      consumption = 1000.000, price = 0.35, base_fee_monthly = 12.00
      full-year cost = 1000 * 0.35 + 12.00 * (11 + 30/31) = 350.00 + 143.61 = 493.61

    Diff = 1200.00 - 493.61 = 706.39
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    _create_advance_payment(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="100.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert data["meter_id"] == meter_id
    assert data["year"] == 2023
    assert data["cost_basis"] == "actual"
    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("493.61")
    assert Decimal(data["total_advance_payments"]) == Decimal("1200.00")
    assert Decimal(data["difference"]) == Decimal("706.39")
    assert data["message"] is None


def test_diff_no_advance_payments(client):
    """200 with total_advance_payments = null when no advance payment exists."""
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("493.61")
    assert data["cost_basis"] == "actual"
    assert data["total_advance_payments"] is None
    assert data["difference"] is None
    assert data["message"] == "Kein Abschlag für dieses Jahr hinterlegt."


def test_diff_partial_year_advance_payment(client):
    """Advance payment covers only part of the year; total is 6 full months.

    Advance payment: 100.00/month, valid 2023-07-01..2023-12-31
    Overlap with year: 6 full months (Jul to Dec)
    Expected total: 6 * 100.00 = 600.00

    Yearly cost (same as above): 493.61
    Diff = 600.00 - 493.61 = 106.39
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    _create_advance_payment(
        client, meter_id,
        valid_from="2023-07-01", valid_to="2023-12-31",
        monthly_amount="100.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_advance_payments"]) == Decimal("600.00")
    assert Decimal(data["difference"]) == Decimal("106.39")


def test_diff_mid_year_amount_change(client):
    """Advance payment amount changes mid-year; both periods cover full months.

    Period 1: 80.00/month, 2023-01-01..2023-06-30 (6 full months)
      contribution = 6 * 80.00 = 480.00
    Period 2: 120.00/month, 2023-07-01..2023-12-31 (6 full months)
      contribution = 6 * 120.00 = 720.00

    Total = 480.00 + 720.00 = 1200.00
    Yearly cost = 493.61
    Diff = 1200.00 - 493.61 = 706.39
    """
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    _create_advance_payment(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-06-30",
        monthly_amount="80.00",
    )
    _create_advance_payment(
        client, meter_id,
        valid_from="2023-07-01", valid_to="2023-12-31",
        monthly_amount="120.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_advance_payments"]) == Decimal("1200.00")
    assert Decimal(data["difference"]) == Decimal("706.39")


def test_diff_meter_not_found(client):
    """404 when the meter does not exist."""
    response = call_diff(client, 999999, 2023)
    assert response.status_code == 404
    assert "Meter mit ID" in response.json()["detail"]


def test_diff_invalid_year(client):
    """422 when the year is outside the 2000-2100 range."""
    meter_id = _create_meter(client)

    response = call_diff(client, meter_id, 1999)
    assert response.status_code == 422
    assert "Jahr" in response.json()["detail"]

    response = call_diff(client, meter_id, 2101)
    assert response.status_code == 422
    assert "Jahr" in response.json()["detail"]


def test_diff_no_advance_payment_and_no_tariff(client):
    """Both cost projection and advance payment missing; messages combined."""
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert data["estimated_or_actual_cost"] is None
    assert data["cost_basis"] is None
    assert data["total_advance_payments"] is None
    assert data["difference"] is None
    assert "Kein gültiger Tarif für diesen Zeitraum gefunden" in data["message"]
    assert "Kein Abschlag für dieses Jahr hinterlegt" in data["message"]


def test_diff_open_ended_advance_payment(client):
    """Open-ended advance payment (no valid_to) covers the full year if still active.
    Same result as test_diff_completed_year_full_advance_payment."""
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    _create_advance_payment(
        client, meter_id,
        valid_from="2022-01-01", valid_to=None,
        monthly_amount="100.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_advance_payments"]) == Decimal("1200.00")
    assert Decimal(data["difference"]) == Decimal("706.39")


def test_diff_wastewater_completed_year(client):
    """Wastewater diff with completed year, with garden meter.

    Cold water: readings 1000.000 (2022-12-31), 1500.000 (2023-12-31) -> 500 m³
    Garden water: readings 200.000 (2022-12-31), 250.000 (2023-12-31) -> 50 m³
    Wastewater: 500 - 50 = 450 m³

    Tariff: wastewater, 4.00/m³, base_fee_monthly = 15.00
    Full-year cost = 450 * 4.00 + 15.00 * (11 + 30/31) = 1800 + 179.52 = 1979.52

    Advance payment: 160.00/month, full year = 12 * 160.00 = 1920.00
    Diff = 1920.00 - 1979.52 = -59.52 (Nachzahlung)
    """
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")

    _create_reading(client, cold_meter_id, "1000.000", "2022-12-31")
    _create_reading(client, cold_meter_id, "1500.000", "2023-12-31")
    _create_reading(client, garden_meter_id, "200.000", "2022-12-31")
    _create_reading(client, garden_meter_id, "250.000", "2023-12-31")

    _create_tariff(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="4.00000", base_fee_monthly="15.00",
        tariff_kind="wastewater",
    )

    _create_wastewater_advance_payment(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="160.00",
        water_garden_meter_id=garden_meter_id,
    )

    response = call_diff_wastewater(
        client, cold_meter_id, 2023, "2024-01-15", water_garden_meter_id=garden_meter_id,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["meter_id"] == cold_meter_id
    assert data["year"] == 2023
    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("1979.52")
    assert Decimal(data["total_advance_payments"]) == Decimal("1920.00")
    assert Decimal(data["difference"]) == Decimal("-59.52")


def test_diff_wastewater_no_garden_meter(client):
    """Wastewater diff without garden meter - all cold water counts as wastewater.

    Cold water: 500 m³ (same readings)
    No garden meter -> garden consumption = 0
    Wastewater = 500 - 0 = 500 m³

    Tariff: 4.00/m³, base_fee_monthly = 15.00
    Full-year cost = 500 * 4.00 + 15.00 * (11 + 30/31) = 2000.00 + 179.52 = 2179.52

    Advance payment: 180.00/month = 12 * 180.00 = 2160.00
    Diff = 2160.00 - 2179.52 = -19.52
    """
    cold_meter_id = _create_meter(client, "water_cold")

    _create_reading(client, cold_meter_id, "1000.000", "2022-12-31")
    _create_reading(client, cold_meter_id, "1500.000", "2023-12-31")

    _create_tariff(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="4.00000", base_fee_monthly="15.00",
        tariff_kind="wastewater",
    )

    _create_wastewater_advance_payment(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="180.00",
    )

    response = call_diff_wastewater(client, cold_meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("2179.52")
    assert Decimal(data["total_advance_payments"]) == Decimal("2160.00")
    assert Decimal(data["difference"]) == Decimal("-19.52")


def test_wastewater_advance_payment_without_garden_meter_uses_full_cold_water_consumption(
    client, db_session
):
    """Wastewater advance payment without garden meter uses full cold water consumption.

    API level: a WASTEWATER advance payment with water_cold_meter_id set and
    water_garden_meter_id omitted (None) must be created successfully.

    Service level: _compute_wastewater_consumption with water_garden_meter_id=None
    returns the full cold water consumption (no garden subtraction). The control
    case with water_garden_meter_id set subtracts the garden consumption.

    Cold water: readings 1000.000 (2022-12-31), 1500.000 (2023-12-31) -> 500 m³
    Garden water: readings 200.000 (2022-12-31), 250.000 (2023-12-31) -> 50 m³
    Without garden meter -> 500 m³, with garden meter -> 500 - 50 = 450 m³
    """
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")

    _create_reading(client, cold_meter_id, "1000.000", "2022-12-31")
    _create_reading(client, cold_meter_id, "1500.000", "2023-12-31")
    _create_reading(client, garden_meter_id, "200.000", "2022-12-31")
    _create_reading(client, garden_meter_id, "250.000", "2023-12-31")

    _create_wastewater_advance_payment(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="160.00",
    )

    consumption_without_garden = _compute_wastewater_consumption(
        db_session, cold_meter_id, None, date(2023, 1, 1), date(2023, 12, 31),
    )
    assert consumption_without_garden == Decimal("500.000")

    consumption_with_garden = _compute_wastewater_consumption(
        db_session, cold_meter_id, garden_meter_id, date(2023, 1, 1), date(2023, 12, 31),
    )
    assert consumption_with_garden == Decimal("450.000")


# ---------------------------------------------------------------------------
# Tests for GET /api/costs/advance-payment-diff-by-category
# ---------------------------------------------------------------------------


def call_diff_by_category(client, category, year, as_of_date=None, meter_id=None,
                          water_cold_meter_id=None, water_garden_meter_id=None):
    params = {"category": category, "year": year}
    if as_of_date is not None:
        params["as_of_date"] = as_of_date
    if meter_id is not None:
        params["meter_id"] = meter_id
    if water_cold_meter_id is not None:
        params["water_cold_meter_id"] = water_cold_meter_id
    if water_garden_meter_id is not None:
        params["water_garden_meter_id"] = water_garden_meter_id
    return client.get("/api/costs/advance-payment-diff-by-category", params=params)


def test_diff_by_category_power_import(client):
    """Happy path: category=power_import returns same data as
    advance-payment-diff with category field."""
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )
    _create_advance_payment(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="100.00",
    )

    response = call_diff_by_category(
        client, category="power_import", year=2023,
        as_of_date="2024-01-15", meter_id=meter_id,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "power_import"
    assert data["meter_id"] == meter_id
    assert data["year"] == 2023
    assert data["cost_basis"] == "actual"
    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("493.61")
    assert Decimal(data["total_advance_payments"]) == Decimal("1200.00")
    assert Decimal(data["difference"]) == Decimal("706.39")


def test_diff_by_category_gas(client):
    """Happy path: category=gas completes successfully."""
    meter_id = _create_meter(client, "gas")
    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.12000", base_fee_monthly="15.00",
        gas_z_zahl="0.95", gas_brennwert="11.0",
    )
    _create_advance_payment(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="80.00", category="gas",
    )

    response = call_diff_by_category(
        client, category="gas", year=2023,
        as_of_date="2024-01-15", meter_id=meter_id,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "gas"
    assert data["meter_id"] == meter_id
    assert data["year"] == 2023


def test_diff_by_category_cold_water(client):
    """Happy path: category=cold_water completes successfully."""
    meter_id = _create_meter(client, "water_cold")
    _create_reading(client, meter_id, "500.000", "2022-12-31")
    _create_reading(client, meter_id, "800.000", "2023-06-30")
    _create_reading(client, meter_id, "1100.000", "2023-12-31")
    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="2.50000", base_fee_monthly="10.00",
    )
    _create_advance_payment(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="50.00", category="cold_water",
    )

    response = call_diff_by_category(
        client, category="cold_water", year=2023,
        as_of_date="2024-01-15", meter_id=meter_id,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "cold_water"
    assert data["meter_id"] == meter_id


def test_diff_by_category_wastewater(client):
    """Happy path: category=wastewater completes successfully."""
    cold_meter_id = _create_meter(client, "water_cold")
    garden_meter_id = _create_meter(client, "water_garden")

    _create_reading(client, cold_meter_id, "1000.000", "2022-12-31")
    _create_reading(client, cold_meter_id, "1500.000", "2023-12-31")
    _create_reading(client, garden_meter_id, "200.000", "2022-12-31")
    _create_reading(client, garden_meter_id, "250.000", "2023-12-31")

    _create_tariff(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="4.00000", base_fee_monthly="15.00",
        tariff_kind="wastewater",
    )
    _create_wastewater_advance_payment(
        client, cold_meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        monthly_amount="160.00",
        water_garden_meter_id=garden_meter_id,
    )

    response = call_diff_by_category(
        client, category="wastewater", year=2023,
        as_of_date="2024-01-15",
        water_cold_meter_id=cold_meter_id,
        water_garden_meter_id=garden_meter_id,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "wastewater"
    assert data["meter_id"] == cold_meter_id
    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("1979.52")
    assert Decimal(data["total_advance_payments"]) == Decimal("1920.00")
    assert Decimal(data["difference"]) == Decimal("-59.52")


def test_diff_by_category_missing_meter_id(client):
    """422 when meter_id is missing for a non-wastewater category."""
    response = call_diff_by_category(
        client, category="power_import", year=2023,
        as_of_date="2024-01-15",
    )
    assert response.status_code == 422
    assert "meter_id ist erforderlich" in response.json()["detail"]


def test_diff_by_category_missing_water_cold_meter_id(client):
    """422 when water_cold_meter_id is missing for wastewater."""
    response = call_diff_by_category(
        client, category="wastewater", year=2023,
        as_of_date="2024-01-15",
    )
    assert response.status_code == 422
    assert "water_cold_meter_id ist erforderlich" in response.json()["detail"]


def test_diff_by_category_both_meter_and_water_cold(client):
    """422 when both meter_id AND water_cold_meter_id are set for wastewater."""
    meter_id = _create_meter(client)
    response = call_diff_by_category(
        client, category="wastewater", year=2023,
        as_of_date="2024-01-15",
        meter_id=meter_id,
        water_cold_meter_id=meter_id,
    )
    assert response.status_code == 422
    assert "meter_id darf nicht gesetzt sein" in response.json()["detail"]


def test_diff_by_category_water_params_for_non_wastewater(client):
    """422 when water_cold_meter_id is set for a non-wastewater category."""
    meter_id = _create_meter(client)
    response = call_diff_by_category(
        client, category="gas", year=2023,
        as_of_date="2024-01-15",
        meter_id=meter_id,
        water_cold_meter_id=999,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "water_cold_meter_id darf nicht gesetzt sein" in detail