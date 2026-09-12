"""
Tests for the years overview endpoint (GET /api/costs/years-overview).

Covers:
- Standalone meter with multiple years
- Replacement chain: predecessor excluded from top-level, readings count
- Meter with no tariff: cost fields null
- Meter with gaps in years: year without readings omitted
- Logical meter resolution: replaced meter not in top-level
- Empty database: empty list
"""
from decimal import Decimal


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


def test_years_overview_single_meter(client):
    """Standalone meter with readings in multiple years returns all years."""
    meter_id = _create_meter(client, label="Strom Zähler")

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1500.000", "2024-06-30")
    _create_reading(client, meter_id, "2000.000", "2024-12-31")
    _create_reading(client, meter_id, "2100.000", "2025-06-30")

    _create_tariff(client, meter_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000", base_fee_monthly="10.00")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    entry = data[0]
    assert entry["meter_id"] == meter_id
    assert entry["meter_label"] == "Strom Zähler"
    assert entry["meter_type"] == "electricity_import"
    assert entry["unit"] == "kWh"

    years = {y["year"]: y for y in entry["years"]}
    assert 2024 in years
    y2024 = years[2024]
    assert y2024["consumption"] is not None
    assert y2024["cost"] is not None
    assert y2024["cost_basis"] == "actual"


def test_years_overview_standalone_multiple_years(client):
    """Standalone meter with two complete years of data."""
    meter_id = _create_meter(client, label="Mehrjährig")

    _create_reading(client, meter_id, "0.000", "2022-12-31")
    _create_reading(client, meter_id, "500.000", "2023-06-30")
    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "2000.000", "2024-12-31")

    _create_tariff(client, meter_id, valid_from="2023-01-01", valid_to=None,
                   price_per_unit="0.25000", base_fee_monthly="8.00")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    entry = data[0]
    years = {y["year"]: y for y in entry["years"]}

    assert 2023 in years
    assert years[2023]["consumption"] is not None
    assert years[2023]["cost"] is not None
    assert years[2023]["cost_basis"] == "actual"
    assert Decimal(years[2023]["consumption"]) == Decimal("1000.000")

    assert 2024 in years
    assert Decimal(years[2024]["consumption"]) == Decimal("1000.000")


def test_years_overview_chain_meter(client):
    """Replacement chain: predecessor excluded from top-level but its readings count."""
    old_id = _create_meter(client, label="Alter Gas Zähler", meter_type="gas")
    new_id = _create_meter(client, label="Neuer Gas Zähler", meter_type="gas",
                           replaces_meter_id=old_id)

    _create_reading(client, old_id, "0.000", "2022-12-31")
    _create_reading(client, old_id, "500.000", "2023-12-31")
    _create_reading(client, old_id, "800.000", "2024-06-30")

    _create_reading(client, new_id, "0.000", "2024-07-01")
    _create_reading(client, new_id, "300.000", "2024-12-31")

    _create_tariff(client, old_id, valid_from="2023-01-01", valid_to=None,
                   price_per_unit="0.10000", base_fee_monthly=None,
                   gas_z_zahl="0.9612", gas_brennwert="11.482")
    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.10000", base_fee_monthly=None,
                   gas_z_zahl="0.9612", gas_brennwert="11.482")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    entry = data[0]
    assert entry["meter_id"] == new_id
    assert entry["meter_label"] == "Neuer Gas Zähler"
    assert entry["meter_type"] == "gas"
    assert entry["unit"] == "m³"

    years = {y["year"]: y for y in entry["years"]}
    assert 2023 in years
    assert 2024 in years
    assert Decimal(years[2023]["consumption"]) == Decimal("500.000")
    assert years[2023]["cost_basis"] == "actual"


def test_years_overview_no_tariff(client):
    """Meter with no consumption tariff returns cost fields as null."""
    meter_id = _create_meter(client, label="Ohne Tarif")

    _create_reading(client, meter_id, "1000.000", "2023-12-31")
    _create_reading(client, meter_id, "1500.000", "2024-12-31")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    entry = data[0]
    assert entry["meter_id"] == meter_id

    years = {y["year"]: y for y in entry["years"]}
    if 2024 in years:
        y2024 = years[2024]
        assert y2024["consumption"] is not None
        assert y2024["cost"] is None
        assert y2024["cost_basis"] is not None


def test_years_overview_gap_in_years(client):
    """Meter with readings in non-consecutive years: year without reading omitted."""
    meter_id = _create_meter(client, label="Lückenhaft")

    _create_reading(client, meter_id, "1000.000", "2022-12-31")
    _create_reading(client, meter_id, "2000.000", "2023-12-31")
    _create_reading(client, meter_id, "2500.000", "2025-06-30")

    _create_tariff(client, meter_id, valid_from="2023-01-01", valid_to=None,
                   price_per_unit="0.30000", base_fee_monthly="10.00")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    entry = data[0]
    years = {y["year"]: y for y in entry["years"]}

    assert 2023 in years
    assert 2024 not in years, "Year without readings should be omitted"
    assert 2025 in years


def test_years_overview_replaced_meter_not_in_top_level(client):
    """A replaced meter should NOT appear as a top-level entry."""
    old_id = _create_meter(client, label="Ersetzt", meter_type="electricity_import")
    _create_meter(client, label="Ersetzer", meter_type="electricity_import",
                  replaces_meter_id=old_id)

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    ids = {entry["meter_id"] for entry in data}
    assert old_id not in ids, "Replaced meter should not appear in top-level entries"


def test_years_overview_empty_database(client):
    """Empty database returns an empty list."""
    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    assert response.json() == []


def test_years_overview_standalone_and_chain_mix(client):
    """Both standalone and chained meters appear in the response."""
    standalone_id = _create_meter(client, label="Standalone")

    old_id = _create_meter(client, label="Kette Alt", meter_type="gas")
    new_id = _create_meter(client, label="Kette Neu", meter_type="gas",
                           replaces_meter_id=old_id)

    _create_reading(client, standalone_id, "1000.000", "2023-12-31")
    _create_reading(client, standalone_id, "1500.000", "2024-12-31")
    _create_tariff(client, standalone_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.30000")

    _create_reading(client, old_id, "0.000", "2023-12-31")
    _create_reading(client, old_id, "500.000", "2024-06-30")
    _create_reading(client, new_id, "0.000", "2024-07-01")
    _create_reading(client, new_id, "400.000", "2024-12-31")
    _create_tariff(client, old_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.10000", gas_z_zahl="0.9612", gas_brennwert="11.482")
    _create_tariff(client, new_id, valid_from="2024-01-01", valid_to=None,
                   price_per_unit="0.10000", gas_z_zahl="0.9612", gas_brennwert="11.482")

    response = client.get("/api/costs/years-overview")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    ids = {entry["meter_id"] for entry in data}
    assert standalone_id in ids
    assert new_id in ids
    assert old_id not in ids