from app.services.tools.soap_tool._lye_water import compute_lye_water_values


def _base_payload(**overrides):
    payload = {
        "oils": [
            {"grams": 500, "sap_koh": 190},
            {"grams": 150, "sap_koh": 180},
        ],
        "selected": "NaOH",
        "superfat_pct": 5,
        "purity_pct": 100,
        "water_method": "percent",
        "water_pct": 33,
        "lye_concentration_input_pct": 33,
        "water_ratio_input": 2,
    }
    payload.update(overrides)
    return payload


def test_percent_mode_water_tracks_oils_total():
    payload = _base_payload()
    result = compute_lye_water_values(**payload)
    # 650 g oils * 33%
    assert round(result["total_oils_g"], 2) == 650.00
    assert round(result["water_g"], 2) == 214.50


def test_concentration_mode_water_changes_with_superfat():
    payload = _base_payload()
    payload["water_method"] = "concentration"
    payload["lye_concentration_input_pct"] = 33

    payload["superfat_pct"] = 5
    result_sf5 = compute_lye_water_values(**payload)

    payload["superfat_pct"] = 1
    result_sf1 = compute_lye_water_values(**payload)

    # Lower superfat means more lye required, so water should increase in concentration mode.
    assert result_sf1["lye_adjusted_g"] > result_sf5["lye_adjusted_g"]
    assert result_sf1["water_g"] > result_sf5["water_g"]


def test_percent_mode_still_returns_water_when_lye_is_zero():
    payload = {
        "oils": [{"grams": 400, "sap_koh": 0}],
        "selected": "NaOH",
        "superfat_pct": 5,
        "purity_pct": 100,
        "water_method": "percent",
        "water_pct": 25,
        "lye_concentration_input_pct": 33,
        "water_ratio_input": 2,
    }
    result = compute_lye_water_values(**payload)
    assert round(result["water_g"], 2) == 100.00


def test_decimal_sap_values_match_mg_sap_values():
    mg_payload = _base_payload()
    mg_payload["water_method"] = "concentration"
    mg_payload["lye_concentration_input_pct"] = 33

    decimal_payload = _base_payload(
        oils=[
            {"grams": 500, "sap_koh": 0.190},
            {"grams": 150, "sap_koh": 0.180},
        ]
    )
    decimal_payload["water_method"] = "concentration"
    decimal_payload["lye_concentration_input_pct"] = 33

    mg_result = compute_lye_water_values(**mg_payload)
    decimal_result = compute_lye_water_values(**decimal_payload)

    assert round(decimal_result["lye_adjusted_g"], 3) == round(
        mg_result["lye_adjusted_g"], 3
    )
    assert round(decimal_result["water_g"], 3) == round(mg_result["water_g"], 3)


def test_lye_is_method_independent_for_same_oils_and_settings():
    base = _base_payload(oils=[{"grams": 650, "sap_koh": 0.188}])

    result_percent = compute_lye_water_values(
        **{**base, "water_method": "percent", "water_pct": 33}
    )
    result_concentration = compute_lye_water_values(
        **{**base, "water_method": "concentration", "lye_concentration_input_pct": 33}
    )
    result_ratio = compute_lye_water_values(
        **{**base, "water_method": "ratio", "water_ratio_input": 2}
    )

    assert round(result_percent["lye_adjusted_g"], 3) == round(
        result_concentration["lye_adjusted_g"], 3
    )
    assert round(result_percent["lye_adjusted_g"], 3) == round(
        result_ratio["lye_adjusted_g"], 3
    )
    assert result_concentration["water_g"] > 100
    assert result_ratio["water_g"] > 100
