from app.services.tools.soap_calculator import SoapToolCalculatorService


def _base_payload(**overrides):
    payload = {
        "oils": [
            {"grams": 500, "sap_koh": 190},
            {"grams": 150, "sap_koh": 180},
        ],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 33, "lye_concentration": 33, "water_ratio": 2},
    }
    payload.update(overrides)
    return payload


def test_percent_mode_water_tracks_oils_total():
    payload = _base_payload()
    result = SoapToolCalculatorService.calculate(payload)
    # 650 g oils * 33%
    assert round(result.total_oils_g, 2) == 650.00
    assert round(result.water_g, 2) == 214.50


def test_concentration_mode_water_changes_with_superfat():
    payload = _base_payload()
    payload["water"]["method"] = "concentration"
    payload["water"]["lye_concentration"] = 33

    payload["lye"]["superfat"] = 5
    result_sf5 = SoapToolCalculatorService.calculate(payload)

    payload["lye"]["superfat"] = 1
    result_sf1 = SoapToolCalculatorService.calculate(payload)

    # Lower superfat means more lye required, so water should increase in concentration mode.
    assert result_sf1.lye_adjusted_g > result_sf5.lye_adjusted_g
    assert result_sf1.water_g > result_sf5.water_g


def test_percent_mode_still_returns_water_when_lye_is_zero():
    payload = {
        "oils": [{"grams": 400, "sap_koh": 0}],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 25},
    }
    result = SoapToolCalculatorService.calculate(payload)
    assert round(result.water_g, 2) == 100.00


def test_decimal_sap_values_match_mg_sap_values():
    mg_payload = _base_payload()
    mg_payload["water"]["method"] = "concentration"
    mg_payload["water"]["lye_concentration"] = 33

    decimal_payload = _base_payload(
        oils=[
            {"grams": 500, "sap_koh": 0.190},
            {"grams": 150, "sap_koh": 0.180},
        ]
    )
    decimal_payload["water"]["method"] = "concentration"
    decimal_payload["water"]["lye_concentration"] = 33

    mg_result = SoapToolCalculatorService.calculate(mg_payload)
    decimal_result = SoapToolCalculatorService.calculate(decimal_payload)

    assert round(decimal_result.lye_adjusted_g, 3) == round(mg_result.lye_adjusted_g, 3)
    assert round(decimal_result.water_g, 3) == round(mg_result.water_g, 3)


def test_lye_is_method_independent_for_same_oils_and_settings():
    base = {
        "oils": [{"grams": 650, "sap_koh": 0.188}],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 33, "lye_concentration": 33, "water_ratio": 2},
    }

    percent_payload = {
        "oils": list(base["oils"]),
        "lye": dict(base["lye"]),
        "water": dict(base["water"], method="percent", water_pct=33),
    }
    concentration_payload = {
        "oils": list(base["oils"]),
        "lye": dict(base["lye"]),
        "water": dict(base["water"], method="concentration", lye_concentration=33),
    }
    ratio_payload = {
        "oils": list(base["oils"]),
        "lye": dict(base["lye"]),
        "water": dict(base["water"], method="ratio", water_ratio=2),
    }

    result_percent = SoapToolCalculatorService.calculate(percent_payload)
    result_concentration = SoapToolCalculatorService.calculate(concentration_payload)
    result_ratio = SoapToolCalculatorService.calculate(ratio_payload)

    assert round(result_percent.lye_adjusted_g, 3) == round(result_concentration.lye_adjusted_g, 3)
    assert round(result_percent.lye_adjusted_g, 3) == round(result_ratio.lye_adjusted_g, 3)
    assert result_concentration.water_g > 100
    assert result_ratio.water_g > 100

