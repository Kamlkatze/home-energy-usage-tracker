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


def _create_tariff(
    client,
    meter_id,
    valid_from,
    valid_to,
    price_per_unit,
    base_fee_monthly="12.50",
    gas_z_zahl=None,
    gas_brennwert=None,
):
    """Create a consumption tariff period via the API.

    base_fee_monthly=None omits the field so the tariff has no base fee.
    gas_z_zahl/gas_brennwert are only included when explicitly provided.
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
    if gas_z_zahl is not None:
        payload["gas_z_zahl"] = gas_z_zahl
    if gas_brennwert is not None:
        payload["gas_brennwert"] = gas_brennwert
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
      base_fee_total  = 12.50 * (22/31 + 1 + 9/31)       = 25.00
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
    """Successful calculation when range spans multiple tariff periods.

    Range: 2024-01-10 to 2024-12-10 (335 days)
    Readings: 1000.000 (2024-01-10), 2500.000 (2024-12-10) -> consumption = 1500.000 kWh
    
Period 1: 2024-01-01 to 2024-06-30 (173 days overlap: Jan 10-31 = 22, Feb-Jun = 151)
          price_per_unit = 0.35490, base_fee_monthly = 12.50
        Period 2: 2024-07-01 to None (162 days overlap: Jul 1 to Dec 9)
          price_per_unit = 0.40000, base_fee_monthly = 15.00
    
    Calculation:
      Consumption allocation:
        Period 1: 1500.000 * 173/335 = 774.626866... kWh
        Period 2: 1500.000 * 162/335 = 725.373134... kWh
      
      Base fee:
        Period 1: 12.50 * 173/30 = 72.083333...
        Period 2: 15.00 * 162/30 = 81.000000
        Total base_fee_total = 153.083333... -> 153.08
      
      Energy cost:
        Period 1: 774.626866 * 0.35490 = 274.822...
        Period 2: 725.373134 * 0.40000 = 290.149...
        Total energy = 564.971...
      
      total_cost = 153.083333 + 565.064328 = 718.147661... -> 718.15 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "2500.000", "2024-12-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-06-30",
        price_per_unit="0.35490",
        base_fee_monthly="12.50",
    )
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-07-01",
        valid_to=None,
        price_per_unit="0.40000",
        base_fee_monthly="15.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-12-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("1500.000")
    assert Decimal(data["price_per_unit"]) == Decimal("0.35490")
    assert Decimal(data["base_fee_total"]) == Decimal("150.73")
    assert Decimal(data["total_cost"]) == Decimal("715.79")



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
    """Base fee is prorated by calendar-accurate month lengths.

    Readings 100.000 (2024-05-01) and 100.000 (2024-05-11):
      prorated days = 10 out of 31 days in May
      base_fee_total = 10.00 * 10/31 = 3.2258... -> 3.23 (ROUND_HALF_UP)
      total_cost     = 0.000 * 0.30000 + 3.2258...     -> 3.23
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
    assert Decimal(data["base_fee_total"]) == Decimal("3.23")
    assert Decimal(data["total_cost"]) == Decimal("3.23")


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


def test_calculate_costs_multiple_periods_different_price_per_unit(client):
    """Cost calculation spanning 2 tariff periods with different price_per_unit only.

    Range: 2024-01-10 to 2024-03-10 (60 days)
    Readings: 1000.000 (2024-01-10), 1150.500 (2024-03-10) -> consumption = 150.500 kWh
    
    Period 1: 2024-01-01 to 2024-02-15 (36 days overlap with range)
      price_per_unit = 0.30000, base_fee_monthly = 10.00
    Period 2: 2024-02-16 to 2024-12-31 (24 days overlap with range)
      price_per_unit = 0.40000, base_fee_monthly = 10.00
    
    Calculation:
      Consumption allocated proportionally by days:
        Period 1: 150.500 * 37/60 = 92.808333... kWh
        Period 2: 150.500 * 23/60 = 57.691666... kWh
      
      Base fee (same for both periods):
        Period 1: 10.00 * 37/30 = 12.333333...
        Period 2: 10.00 * 23/30 = 7.666666...
        Total base_fee_total = 20.000000 -> 20.00
      
      Energy cost:
        Period 1: 92.808333 * 0.30000 = 27.842500
        Period 2: 57.691666 * 0.40000 = 23.076666
        Total energy = 50.919166
      
      total_cost = 20.000000 + 50.919166 = 70.919166 -> 70.92 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    
    # Period 1: Jan 1 to Feb 15
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-15",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    # Period 2: Feb 16 to Dec 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-16",
        valid_to="2024-12-31",
        price_per_unit="0.40000",
        base_fee_monthly="10.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == meter_id
    assert Decimal(data["consumption"]) == Decimal("150.500")
    # Note: price_per_unit in response is the FIRST period's price (for backward compatibility)
    # This matches the existing API contract
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")
    assert Decimal(data["base_fee_total"]) == Decimal("20.00")
    assert Decimal(data["total_cost"]) == Decimal("70.92")


def test_calculate_costs_multiple_periods_different_base_fee_monthly(client):
    """Cost calculation spanning 2 tariff periods with different base_fee_monthly only.

    Range: 2024-01-10 to 2024-03-10 (60 days)
    Readings: 1000.000 (2024-01-10), 1150.500 (2024-03-10) -> consumption = 150.500 kWh
    
    Period 1: 2024-01-01 to 2024-02-15 (37 days overlap: Jan 10-31 = 22, Feb 1-15 = 15)
      price_per_unit = 0.35000, base_fee_monthly = 5.00
    Period 2: 2024-02-16 to 2024-12-31 (23 days overlap: Feb 16-29 = 14, Mar 1-10 = 9)
      price_per_unit = 0.35000, base_fee_monthly = 15.00
    
    Calculation:
      Consumption allocated proportionally by days:
        Period 1: 150.500 * 37/60 = 92.8083... kWh
        Period 2: 150.500 * 23/60 = 57.6916... kWh
      
      Base fee (calendar-accurate months):
        Period 1: 5.00 * (22/31 + 15/29) = 6.1346...
        Period 2: 15.00 * (14/29 + 9/31) = 11.5962...
        Total base_fee_total (rounded): 17.7308... -> 17.73
      
      Energy cost (same price):
        Period 1: 92.8083 * 0.35000 = 32.482905
        Period 2: 57.6916 * 0.35000 = 20.19206
        Total energy = 52.674965
      
      total_cost = 17.7308... + 52.674965 = 70.405773 -> 70.41 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    
    # Period 1: Jan 1 to Feb 15
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-15",
        price_per_unit="0.35000",
        base_fee_monthly="5.00",
    )
    # Period 2: Feb 16 to Dec 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-16",
        valid_to="2024-12-31",
        price_per_unit="0.35000",
        base_fee_monthly="15.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("150.500")
    # Note: price_per_unit in response is the FIRST period's price (for backward compatibility)
    # This matches the existing API contract
    assert Decimal(data["price_per_unit"]) == Decimal("0.35000")
    assert Decimal(data["base_fee_total"]) == Decimal("17.73")
    assert Decimal(data["total_cost"]) == Decimal("70.41")


def test_calculate_costs_multiple_periods_both_values_different(client):
    """Cost calculation spanning 2 tariff periods with both values different.

    Range: 2024-01-10 to 2024-03-10 (60 days)
    Readings: 1000.000 (2024-01-10), 1150.500 (2024-03-10) -> consumption = 150.500 kWh
    
    Period 1: 2024-01-01 to 2024-02-15 (37 days overlap: Jan 10-31 = 22, Feb 1-15 = 15)
      price_per_unit = 0.30000, base_fee_monthly = 5.00
    Period 2: 2024-02-16 to 2024-12-31 (23 days overlap: Feb 16-29 = 14, Mar 1-10 = 9)
      price_per_unit = 0.40000, base_fee_monthly = 15.00
    
    Calculation:
      Consumption allocated proportionally by days:
        Period 1: 150.500 * 37/60 = 92.808333 kWh
        Period 2: 150.500 * 23/60 = 57.691667 kWh
      
      Base fee (calendar-accurate months):
        Period 1: 5.00 * (22/31 + 15/29) = 6.1346...
        Period 2: 15.00 * (14/29 + 9/31) = 11.5962...
        Total base_fee_total (rounded): 17.7308... -> 17.73
      
      Energy cost:
        Period 1: 92.808333 * 0.30000 = 27.842500
        Period 2: 57.691667 * 0.40000 = 23.076667
        Total energy = 50.919167
      
      total_cost = 17.7308... + 50.919167 = 68.649987 -> 68.65 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    
    # Period 1: Jan 1 to Feb 15
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-15",
        price_per_unit="0.30000",
        base_fee_monthly="5.00",
    )
    # Period 2: Feb 16 to Dec 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-16",
        valid_to="2024-12-31",
        price_per_unit="0.40000",
        base_fee_monthly="15.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("150.500")
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")
    assert Decimal(data["base_fee_total"]) == Decimal("17.73")
    assert Decimal(data["total_cost"]) == Decimal("68.65")


def test_calculate_costs_three_periods(client):
    """Cost calculation spanning 3 tariff periods.

    Range: 2024-01-10 to 2024-05-10 (121 days)
    Readings: 1000.000 (2024-01-10), 1300.000 (2024-05-10) -> consumption = 300.000 kWh
    
    Period 1: 2024-01-01 to 2024-02-29 (51 days overlap: Jan 10-31 = 22, Feb 1-29 = 29)
      price_per_unit = 0.30000, base_fee_monthly = 10.00
    Period 2: 2024-03-01 to 2024-03-31 (31 days overlap)
      price_per_unit = 0.35000, base_fee_monthly = 12.00
    Period 3: 2024-04-01 to 2024-12-31 (39 days overlap: Apr 1-30 = 30, May 1-9 = 9)
      price_per_unit = 0.40000, base_fee_monthly = 15.00
    
    Calculation:
      Total days in range = 121
      Consumption allocation:
        Period 1: 300.000 * 51/121 = 126.4463... kWh
        Period 2: 300.000 * 31/121 = 76.8595... kWh
        Period 3: 300.000 * 39/121 = 96.6942... kWh
      
      Base fee (calendar-accurate months):
        Period 1: 10.00 * (22/31 + 1) = 17.0968...
        Period 2: 12.00 * 1 = 12.0000
        Period 3: 15.00 * (1 + 9/31) = 19.3548...
        Total base_fee_total: 48.4516... -> 48.45
      
      Energy cost:
        Period 1: 126.4463 * 0.30000 = 37.9339
        Period 2: 76.8595 * 0.35000 = 26.9008
        Period 3: 96.6942 * 0.40000 = 38.6777
        Total energy = 103.5124
      
      total_cost = 48.4516 + 103.5124 = 151.9640 -> 151.96 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1300.000", "2024-05-10")
    
    # Period 1: Jan 1 to Feb 29 (leap year)
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-29",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    # Period 2: Mar 1 to Mar 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-03-01",
        valid_to="2024-03-31",
        price_per_unit="0.35000",
        base_fee_monthly="12.00",
    )
    # Period 3: Apr 1 to Dec 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-04-01",
        valid_to="2024-12-31",
        price_per_unit="0.40000",
        base_fee_monthly="15.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-05-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("300.000")
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")  # First period's price
    assert Decimal(data["base_fee_total"]) == Decimal("48.45")
    assert Decimal(data["total_cost"]) == Decimal("151.96")


def test_calculate_costs_period_boundary_at_from(client):
    """Cost calculation where 'from' date falls exactly on a tariff period boundary.

    Range: 2024-02-01 to 2024-03-10 (38 days)
    Readings: 1000.000 (2024-02-01), 1100.000 (2024-03-10) -> consumption = 100.000 kWh
    
    Period 1: 2024-01-01 to 2024-01-31 (0 days overlap - from is exactly at start of period 2)
    Period 2: 2024-02-01 to 2024-02-29 (29 days overlap)
      price_per_unit = 0.30000, base_fee_monthly = 10.00
    Period 3: 2024-03-01 to 2024-12-31 (9 days overlap)
      price_per_unit = 0.40000, base_fee_monthly = 12.00
    
    Calculation:
      Total days in range = 38
      Consumption allocation:
        Period 2: 100.000 * 29/38 = 76.3158... kWh
        Period 3: 100.000 * 9/38 = 23.6842... kWh
      
      Base fee (calendar-accurate months):
        Period 2: 10.00 * 1 (full Feb) = 10.0000
        Period 3: 12.00 * 9/31 = 3.4839
        Total base_fee_total = 13.4839 -> 13.48
      
      Energy cost:
        Period 2: 76.3158 * 0.30000 = 22.8947
        Period 3: 23.6842 * 0.40000 = 9.4737
        Total energy = 32.3684
      
      total_cost = 13.4839 + 32.3684 = 45.8523 -> 45.85 (ROUND_HALF_UP)
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-02-01")
    _create_reading(client, meter_id, "1100.000", "2024-03-10")
    
    # Period 1: Jan 1 to Jan 31 (doesn't overlap with range)
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-01-31",
        price_per_unit="0.25000",
        base_fee_monthly="5.00",
    )
    # Period 2: Feb 1 to Feb 29
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-01",
        valid_to="2024-02-29",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    # Period 3: Mar 1 to Dec 31
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-03-01",
        valid_to="2024-12-31",
        price_per_unit="0.40000",
        base_fee_monthly="12.00",
    )

    response = _calculate(client, meter_id, "2024-02-01", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("100.000")
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")  # First overlapping period's price
    assert Decimal(data["base_fee_total"]) == Decimal("13.48")
    assert Decimal(data["total_cost"]) == Decimal("45.85")


def test_calculate_costs_period_boundary_at_to(client):
    """Cost calculation where 'to' date falls exactly on a tariff period boundary.

    Range: 2024-01-10 to 2024-02-29 (50 days)
    Readings: 1000.000 (2024-01-10), 1100.000 (2024-02-29) -> consumption = 100.000 kWh
    
    Period 1: 2024-01-01 to 2024-02-29 (50 days overlap)
      price_per_unit = 0.30000, base_fee_monthly = 10.00
    Period 2: 2024-03-01 to 2024-12-31 (0 days overlap - to is exactly at end of period 1)
    
    Calculation:
      Total days in range = 50
      Only Period 1 overlaps
      Base fee: 10.00 * (22/31 + 28/29) = 16.7519 -> 16.75
      Energy cost: 100.000 * 0.30000 = 30.00
      total_cost = 46.75
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-29")
    
    # Period 1: Jan 1 to Feb 29
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-29",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    # Period 2: Mar 1 to Dec 31 (doesn't overlap with range)
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-03-01",
        valid_to="2024-12-31",
        price_per_unit="0.40000",
        base_fee_monthly="12.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-29")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("100.000")
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")
    assert Decimal(data["base_fee_total"]) == Decimal("16.75")
    assert Decimal(data["total_cost"]) == Decimal("46.75")


def test_calculate_costs_open_ended_period(client):
    """Cost calculation with an open-ended tariff period (valid_to = NULL).

    Range: 2024-01-10 to 2024-03-10 (60 days)
    Readings: 1000.000 (2024-01-10), 1150.500 (2024-03-10) -> consumption = 150.500 kWh
    
    Period 1: 2024-01-01 to 2024-02-15 (37 days overlap: Jan 10-31 = 22, Feb 1-15 = 15)
      price_per_unit = 0.30000, base_fee_monthly = 10.00
    Period 2: 2024-02-16 to NULL (open-ended, 23 days overlap: Feb 16-29 = 14, Mar 1-10 = 9)
      price_per_unit = 0.40000, base_fee_monthly = 15.00
    
    Base fee (calendar-accurate months):
      Period 1: 10.00 * (22/31 + 15/29) = 12.2692...
      Period 2: 15.00 * (14/29 + 9/31) = 11.5962...
      Total: 23.8654 -> 23.87
    """
    meter_id = _create_meter(client)
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.500", "2024-03-10")
    
    # Period 1: Jan 1 to Feb 15
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-15",
        price_per_unit="0.30000",
        base_fee_monthly="10.00",
    )
    # Period 2: Feb 16 to NULL (open-ended)
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-16",
        valid_to=None,
        price_per_unit="0.40000",
        base_fee_monthly="15.00",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("150.500")
    assert Decimal(data["price_per_unit"]) == Decimal("0.30000")
    assert Decimal(data["base_fee_total"]) == Decimal("23.87")
    assert Decimal(data["total_cost"]) == Decimal("74.78")


def test_calculate_costs_gas_conversion_applied(client):
    """Gas meter consumption (m³) is converted to kWh before billing.

    Range: 2024-01-10 to 2024-02-10 (31 days)
    Readings: 1000.000 (2024-01-10), 1100.000 (2024-02-10) -> consumption = 100.000 m³

    Tariff: price_per_unit = 0.10000 €/kWh, no base fee
      gas_z_zahl   = 0.9612
      gas_brennwert = 11.482 kWh/m³

    Calculation:
      kWh = 100.000 m³ * 0.9612 * 11.482 = 1103.649840 kWh
      energy cost = 1103.649840 * 0.10000 = 110.364984 -> 110.36
      base_fee_total = 0.00
      total_cost = 110.36

    The raw consumption reported stays in the meter's unit (m³).
    """
    meter_id = _create_meter(client, meter_type="gas")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-10")

    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "m³"
    # Raw consumption stays in m³; only the billing amount is converted.
    assert Decimal(data["consumption"]) == Decimal("100.000")
    assert Decimal(data["price_per_unit"]) == Decimal("0.10000")
    assert Decimal(data["base_fee_total"]) == Decimal("0.00")
    assert Decimal(data["total_cost"]) == Decimal("110.36")


def test_calculate_costs_gas_missing_z_zahl(client):
    """422 when a gas tariff period lacks gas_z_zahl."""
    meter_id = _create_meter(client, meter_type="gas")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_brennwert="11.482",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-10")

    assert response.status_code == 422
    assert "gas_z_zahl" in response.json()["detail"]
    assert "gas_brennwert" in response.json()["detail"]


def test_calculate_costs_gas_missing_brennwert(client):
    """422 when a gas tariff period lacks gas_brennwert."""
    meter_id = _create_meter(client, meter_type="gas")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-10")

    assert response.status_code == 422
    assert "gas_z_zahl" in response.json()["detail"]
    assert "gas_brennwert" in response.json()["detail"]


def test_calculate_costs_gas_missing_both_fields(client):
    """422 when a gas tariff period has neither conversion factor."""
    meter_id = _create_meter(client, meter_type="gas")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.10000",
        base_fee_monthly=None,
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-10")

    assert response.status_code == 422
    assert "gas_z_zahl" in response.json()["detail"]
    assert "gas_brennwert" in response.json()["detail"]


def test_calculate_costs_non_gas_unaffected_by_gas_fields(client):
    """Gas conversion must NOT apply to non-gas meters.

    An electricity meter's tariff carries gas conversion factors; the cost
    must still be raw kWh * price_per_unit (no m³->kWh conversion).
    """
    meter_id = _create_meter(client)  # electricity_import -> unit kWh
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1100.000", "2024-02-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-12-31",
        price_per_unit="0.35490",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-02-10")

    assert response.status_code == 200
    data = response.json()
    assert data["unit"] == "kWh"
    assert Decimal(data["consumption"]) == Decimal("100.000")
    assert Decimal(data["base_fee_total"]) == Decimal("0.00")
    # 100 kWh * 0.35490 = 35.49 (if conversion wrongly applied: 391.69)
    assert Decimal(data["total_cost"]) == Decimal("35.49")


def test_calculate_costs_gas_split_across_periods(client):
    """Gas consumption split across two tariff periods with different factors.

    Range: 2024-01-10 to 2024-03-10 (60 days)
    Readings: 1000.000 (2024-01-10), 1150.000 (2024-03-10) -> consumption = 150.000 m³

    Period 1: 2024-01-01 to 2024-02-15 (37 days overlap)
      price_per_unit = 0.10000, base_fee_monthly = None
      gas_z_zahl = 0.9612, gas_brennwert = 11.482
    Period 2: 2024-02-16 to 2024-12-31 (23 days overlap)
      price_per_unit = 0.15000, base_fee_monthly = None
      gas_z_zahl = 0.9520, gas_brennwert = 11.250

    Calculation (each period's share converted with its OWN factors):
      Share 1: 150.000 * 37/60 = 92.500 m³
        -> 92.500 * 0.9612 * 11.482 = 1020.876102 kWh
        energy = 1020.876102 * 0.10000 = 102.087610
      Share 2: 150.000 * 23/60 = 57.500 m³
        -> 57.500 * 0.9520 * 11.250 = 615.825000 kWh
        energy = 615.825000 * 0.15000 = 92.373750
      Total energy = 194.461360 -> 194.46
      base_fee_total = 0.00
      total_cost = 194.46
    """
    meter_id = _create_meter(client, meter_type="gas")
    _create_reading(client, meter_id, "1000.000", "2024-01-10")
    _create_reading(client, meter_id, "1150.000", "2024-03-10")
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-01-01",
        valid_to="2024-02-15",
        price_per_unit="0.10000",
        base_fee_monthly=None,
        gas_z_zahl="0.9612",
        gas_brennwert="11.482",
    )
    _create_tariff(
        client,
        meter_id,
        valid_from="2024-02-16",
        valid_to="2024-12-31",
        price_per_unit="0.15000",
        base_fee_monthly=None,
        gas_z_zahl="0.9520",
        gas_brennwert="11.250",
    )

    response = _calculate(client, meter_id, "2024-01-10", "2024-03-10")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["consumption"]) == Decimal("150.000")
    assert Decimal(data["base_fee_total"]) == Decimal("0.00")
    assert Decimal(data["total_cost"]) == Decimal("194.46")