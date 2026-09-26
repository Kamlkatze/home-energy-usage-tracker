"""
Tests for the EEG 2009 feed-in compensation endpoint
(GET /api/electricity/feed-in-compensation).

EEG 2009 § 33 Abs. 2 formula (see Anforderungen.md):
  P = production_consumption
  E = export_consumption
  S = max(0, P - E)  (self-consumption)
  tier1_kwh = min(S, 0.3 * P)
  tier2_kwh = max(0, S - 0.3 * P)
  gross_compensation = P * price_per_unit - tier1_kwh * eeg_tier1_rate - tier2_kwh * eeg_tier2_rate
  metering_point_fee_deducted = days * metering_point_fee_yearly / 365
  Total = gross_compensation - metering_point_fee_deducted
"""
from decimal import Decimal


def _create_meter(client, meter_type):
    response = client.post(
        "/api/meters/", json={"meter_type": meter_type, "label": f"{meter_type} meter"}
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_reading(client, meter_id, value, reading_date):
    response = client.post(
        "/api/readings/",
        json={"meter_id": meter_id, "value": value, "reading_date": reading_date},
    )
    assert response.status_code == 200


def _create_eeg_tariff(
    client, meter_id, valid_from, valid_to, price_per_unit,
    eeg_tier1_rate="0.15000", eeg_tier2_rate="0.10000",
    metering_point_fee_yearly="50.00",
):
    payload = {
        "meter_id": meter_id,
        "tariff_kind": "feed_in_eeg2009",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "price_per_unit": price_per_unit,
        "eeg_tier1_rate": eeg_tier1_rate,
        "eeg_tier2_rate": eeg_tier2_rate,
        "metering_point_fee_yearly": metering_point_fee_yearly,
    }
    response = client.post("/api/tariffs/", json=payload)
    assert response.status_code == 200


def _calculate_compensation(
    client, production_meter_id, export_meter_id, from_, to,
    import_meter_id=None,
):
    params = {
        "production_meter_id": production_meter_id,
        "export_meter_id": export_meter_id,
        "from": from_,
        "to": to,
    }
    if import_meter_id is not None:
        params["import_meter_id"] = import_meter_id
    return client.get("/api/electricity/feed-in-compensation", params=params)


def test_feed_in_compensation_self_consumption_under_30_percent(client):
    """Normalfall: Selbstverbrauch < 30% von P, nur Tier-1 relevant.

    P=1000, E=800 => S=200 (20% of P)
    30% threshold = 300 => tier1=200, tier2=0
    days = (2024-03-10 - 2024-01-10).days = 60
    Total = 1000 * 0.24430 - 200 * 0.15000 - 0 - 60 * 50.00 / 365
          = 244.30 - 30.00 - 8.219178...
          = 206.08 (rounded)
    """
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")

    _create_reading(client, prod_id, "0.000", "2024-01-10")
    _create_reading(client, prod_id, "1000.000", "2024-03-10")
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "800.000", "2024-03-10")

    _create_eeg_tariff(
        client, exp_id,
        valid_from="2024-01-01", valid_to="2024-12-31",
        price_per_unit="0.24430",
    )

    response = _calculate_compensation(client, prod_id, exp_id, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    assert data["production_meter_id"] == prod_id
    assert data["export_meter_id"] == exp_id
    assert data["from_date"] == "2024-01-10"
    assert data["to_date"] == "2024-03-10"
    assert Decimal(data["production_consumption"]) == Decimal("1000.000")
    assert Decimal(data["export_consumption"]) == Decimal("800.000")
    assert Decimal(data["self_consumption"]) == Decimal("200.000")
    assert Decimal(data["tier1_kwh"]) == Decimal("200.000")
    assert Decimal(data["tier2_kwh"]) == Decimal("0.000")
    assert Decimal(data["total_compensation"]) == Decimal("206.08")
    assert Decimal(data["gross_compensation"]) == Decimal("214.30")
    assert Decimal(data["metering_point_fee_deducted"]) == Decimal("8.22")
    assert (
        Decimal(data["total_compensation"])
        == Decimal(data["gross_compensation"]) - Decimal(data["metering_point_fee_deducted"])
    )


def test_feed_in_compensation_self_consumption_over_30_percent(client):
    """Selbstverbrauch > 30% von P: Tier-1 + Tier-2 beide relevant.

    P=1000, E=400 => S=600 (60% of P)
    30% threshold = 300 => tier1=300, tier2=300
    days = 60
    Total = 1000 * 0.24430 - 300 * 0.15000 - 300 * 0.10000 - 60 * 50.00 / 365
          = 244.30 - 45.00 - 30.00 - 8.219178...
          = 161.08 (rounded)
    """
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")

    _create_reading(client, prod_id, "0.000", "2024-01-10")
    _create_reading(client, prod_id, "1000.000", "2024-03-10")
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "400.000", "2024-03-10")

    _create_eeg_tariff(
        client, exp_id,
        valid_from="2024-01-01", valid_to="2024-12-31",
        price_per_unit="0.24430",
    )

    response = _calculate_compensation(client, prod_id, exp_id, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["production_consumption"]) == Decimal("1000.000")
    assert Decimal(data["export_consumption"]) == Decimal("400.000")
    assert Decimal(data["self_consumption"]) == Decimal("600.000")
    assert Decimal(data["tier1_kwh"]) == Decimal("300.000")
    assert Decimal(data["tier2_kwh"]) == Decimal("300.000")
    assert Decimal(data["total_compensation"]) == Decimal("161.08")
    assert Decimal(data["gross_compensation"]) == Decimal("169.30")
    assert Decimal(data["metering_point_fee_deducted"]) == Decimal("8.22")
    assert (
        Decimal(data["total_compensation"])
        == Decimal(data["gross_compensation"]) - Decimal(data["metering_point_fee_deducted"])
    )


def test_feed_in_compensation_self_consumption_exactly_30_percent(client):
    """Randfall: Selbstverbrauch = genau 30% von P.

    P=1000, E=700 => S=300 (= 30% of P)
    tier1=300, tier2=0
    Total = 1000 * 0.24430 - 300 * 0.15000 - 0 - 60 * 50.00 / 365
          = 244.30 - 45.00 - 8.219178...
          = 191.08 (rounded)
    """
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")

    _create_reading(client, prod_id, "0.000", "2024-01-10")
    _create_reading(client, prod_id, "1000.000", "2024-03-10")
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "700.000", "2024-03-10")

    _create_eeg_tariff(
        client, exp_id,
        valid_from="2024-01-01", valid_to="2024-12-31",
        price_per_unit="0.24430",
    )

    response = _calculate_compensation(client, prod_id, exp_id, "2024-01-10", "2024-03-10")
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["self_consumption"]) == Decimal("300.000")
    assert Decimal(data["tier1_kwh"]) == Decimal("300.000")
    assert Decimal(data["tier2_kwh"]) == Decimal("0.000")
    assert Decimal(data["total_compensation"]) == Decimal("191.08")
    assert Decimal(data["gross_compensation"]) == Decimal("199.30")
    assert Decimal(data["metering_point_fee_deducted"]) == Decimal("8.22")
    assert (
        Decimal(data["total_compensation"])
        == Decimal(data["gross_compensation"]) - Decimal(data["metering_point_fee_deducted"])
    )


def test_feed_in_compensation_no_tariff_returns_404(client):
    """404 wenn kein feed_in_eeg2009-Tarif hinterlegt ist.

    Nur ein consumption-Tarif existiert, kein EEG-Tarif.
    """
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")

    _create_reading(client, prod_id, "0.000", "2024-01-10")
    _create_reading(client, prod_id, "1000.000", "2024-03-10")
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "500.000", "2024-03-10")

    # Only a consumption tariff, no EEG tariff
    client.post(
        "/api/tariffs/",
        json={
            "meter_id": exp_id,
            "tariff_kind": "consumption",
            "valid_from": "2024-01-01",
            "valid_to": "2024-12-31",
            "price_per_unit": "0.30000",
        },
    )

    response = _calculate_compensation(client, prod_id, exp_id, "2024-01-10", "2024-03-10")
    assert response.status_code == 404
    assert "EEG 2009" in response.json()["detail"]


def test_feed_in_compensation_meter_not_found_returns_404(client):
    """404 wenn einer der Meter nicht existiert."""
    response = _calculate_compensation(
        client, production_meter_id=99999, export_meter_id=99998,
        from_="2024-01-10", to="2024-03-10",
    )
    assert response.status_code == 404
    assert "nicht gefunden" in response.json()["detail"]


def test_feed_in_compensation_production_meter_no_readings_returns_404(client):
    """404 wenn der Produktionszähler keine Zählerstände im Zeitraum hat."""
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")
    # Reading only on export, not on production
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "500.000", "2024-03-10")

    response = _calculate_compensation(client, prod_id, exp_id, "2024-01-10", "2024-03-10")
    assert response.status_code == 404
    assert "Zählerstand" in response.json()["detail"]


def test_feed_in_compensation_from_after_to_returns_422(client):
    """422 wenn from > to."""
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")

    response = _calculate_compensation(client, prod_id, exp_id, "2024-03-10", "2024-01-10")
    assert response.status_code == 422
    assert "Ungültiger Zeitraum" in response.json()["detail"]


def test_feed_in_compensation_with_import_meter_id(client):
    """import_meter_id wird entgegengenommen aber nicht verwendet (EEG-Formel
    nutzt nur P und E). Prüft, dass der Parameter nicht abstürzt."""
    prod_id = _create_meter(client, "electricity_production")
    exp_id = _create_meter(client, "electricity_export")
    imp_id = _create_meter(client, "electricity_import")

    _create_reading(client, prod_id, "0.000", "2024-01-10")
    _create_reading(client, prod_id, "1000.000", "2024-03-10")
    _create_reading(client, exp_id, "0.000", "2024-01-10")
    _create_reading(client, exp_id, "800.000", "2024-03-10")

    _create_eeg_tariff(
        client, exp_id,
        valid_from="2024-01-01", valid_to="2024-12-31",
        price_per_unit="0.24430",
    )

    response = _calculate_compensation(
        client, prod_id, exp_id, "2024-01-10", "2024-03-10",
        import_meter_id=imp_id,
    )
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["total_compensation"]) == Decimal("206.08")
    assert Decimal(data["gross_compensation"]) == Decimal("214.30")
    assert Decimal(data["metering_point_fee_deducted"]) == Decimal("8.22")
    assert (
        Decimal(data["total_compensation"])
        == Decimal(data["gross_compensation"]) - Decimal(data["metering_point_fee_deducted"])
    )


def test_feed_in_compensation_query_parameter_alias(client):
    """Der Endpoint wird unter den Query-Namen 'production_meter_id',
    'export_meter_id', 'import_meter_id', 'from' und 'to' exponiert."""
    openapi = client.get("/api/openapi.json").json()
    params = openapi["paths"]["/api/electricity/feed-in-compensation"]["get"]["parameters"]
    param_names = sorted(p["name"] for p in params)

    assert param_names == [
        "export_meter_id",
        "from",
        "import_meter_id",
        "production_meter_id",
        "to",
    ]