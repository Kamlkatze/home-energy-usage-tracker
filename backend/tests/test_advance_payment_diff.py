"""
Tests for the advance payment diff endpoint (GET /api/costs/advance-payment-diff).
"""
from decimal import Decimal


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
    gas_z_zahl=None, gas_brennwert=None,
):
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
    assert response.status_code == 200


def _create_advance_payment(client, meter_id, valid_from, valid_to, monthly_amount):
    payload = {
        "meter_id": meter_id,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "monthly_amount": monthly_amount,
    }
    response = client.post("/api/advance-payments/", json=payload)
    assert response.status_code == 200


def call_diff(client, meter_id, year, as_of_date=None):
    params = {"meter_id": meter_id, "year": year}
    if as_of_date is not None:
        params["as_of_date"] = as_of_date
    return client.get("/api/costs/advance-payment-diff", params=params)


def test_diff_completed_year_full_advance_payment(client):
    """Happy path: completed year (2023), single advance payment covering the full year.

    Advance payment: 100.00/month, valid 2023-01-01..2023-12-31
    Expected total: 100 * 365 / 30 = 1216.6667 -> 1216.67

    Yearly cost (same setup as test_yearly_projection_completed_year):
      consumption = 1000.000, price = 0.35, base_fee_monthly = 12.00
      full-year cost = 1000 * 0.35 + 12.00 * 364/30 = 350.00 + 145.60 = 495.60

    Diff = 1216.67 - 495.60 = 721.07
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
    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("495.60")
    assert Decimal(data["total_advance_payments"]) == Decimal("1216.67")
    assert Decimal(data["difference"]) == Decimal("721.07")
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

    assert Decimal(data["estimated_or_actual_cost"]) == Decimal("495.60")
    assert data["cost_basis"] == "actual"
    assert data["total_advance_payments"] is None
    assert data["difference"] is None
    assert data["message"] == "Kein Abschlag für dieses Jahr hinterlegt."


def test_diff_partial_year_advance_payment(client):
    """Advance payment covers only part of the year; total is prorated by days.

    Advance payment: 100.00/month, valid 2023-07-01..2023-12-31
    Overlap with year: 184 days (Jul 1 to Dec 31 inclusive)
    Expected total: 100 * 184 / 30 = 613.3333 -> 613.33

    Yearly cost (same as above): 495.60
    Diff = 613.33 - 495.60 = 117.73
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

    assert Decimal(data["total_advance_payments"]) == Decimal("613.33")
    assert Decimal(data["difference"]) == Decimal("117.73")


def test_diff_mid_year_amount_change(client):
    """Advance payment amount changes mid-year; both periods are prorated.

    Period 1: 80.00/month, 2023-01-01..2023-06-30 (181 days)
      contribution = 80 * 181 / 30 = 482.6667 -> 482.67
    Period 2: 120.00/month, 2023-07-01..2023-12-31 (184 days)
      contribution = 120 * 184 / 30 = 736.00

    Total = 482.67 + 736.00 = 1218.67
    Yearly cost = 495.60
    Diff = 1218.67 - 495.60 = 723.07
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

    assert Decimal(data["total_advance_payments"]) == Decimal("1218.67")
    assert Decimal(data["difference"]) == Decimal("723.07")


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

    # No tariff created -> cost fails
    # No advance payment -> "Kein Abschlag" message

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
    """Open-ended advance payment (no valid_to) covers the full year if still active."""
    meter_id = _create_meter(client)

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "1500.000", "2023-06-30")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")

    _create_tariff(
        client, meter_id,
        valid_from="2023-01-01", valid_to="2023-12-31",
        price_per_unit="0.35000", base_fee_monthly="12.00",
    )

    # Open-ended from 2022-01-01, no end date -> still active in 2023
    _create_advance_payment(
        client, meter_id,
        valid_from="2022-01-01", valid_to=None,
        monthly_amount="100.00",
    )

    response = call_diff(client, meter_id, 2023, "2024-01-15")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_advance_payments"]) == Decimal("1216.67")
    assert Decimal(data["difference"]) == Decimal("721.07")