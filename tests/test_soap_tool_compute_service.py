from app.services.tools.soap_tool import SoapToolComputationService
from app.services.tools.soap_tool._advisory import run_quality_nudge


def _payload(method="percent"):
    return {
        "oils": [
            {
                "name": "Olive Oil",
                "grams": 500,
                "sap_koh": 0.188,
                "iodine": 84,
                "fatty_profile": {
                    "palmitic": 14,
                    "stearic": 3,
                    "oleic": 69,
                    "linoleic": 12,
                    "linolenic": 2,
                },
            },
            {
                "name": "Coconut Oil 76",
                "grams": 150,
                "sap_koh": 0.257,
                "iodine": 10,
                "fatty_profile": {
                    "lauric": 48,
                    "myristic": 19,
                    "palmitic": 9,
                    "stearic": 3,
                    "oleic": 8,
                    "linoleic": 2,
                },
            },
        ],
        "fragrances": [{"name": "Lavender EO", "pct": 3}],
        "additives": {
            "lactate_pct": 1,
            "sugar_pct": 1,
            "salt_pct": 0.5,
            "citric_pct": 0,
        },
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": method, "water_pct": 33, "lye_concentration": 33, "water_ratio": 2},
        "meta": {"unit_display": "g"},
    }


def test_compute_service_returns_full_bundle():
    result = SoapToolComputationService.calculate(_payload())
    assert result["lye_adjusted_g"] > 0
    assert result["water_g"] > 0
    assert result["results_card"]["batch_yield_g"] > result["total_oils_g"]
    assert result["additives"]["fragranceG"] > 0
    assert "quality_report" in result
    assert "warnings" in result["quality_report"]
    assert "visual_guidance" in result["quality_report"]
    assert "blend_tips" in result["quality_report"]
    assert "export" in result
    assert isinstance(result["export"]["csv_rows"], list)
    assert "<html" in result["export"]["sheet_html"].lower()


def test_compute_service_lye_is_method_independent():
    percent = SoapToolComputationService.calculate(_payload(method="percent"))
    concentration = SoapToolComputationService.calculate(_payload(method="concentration"))
    ratio = SoapToolComputationService.calculate(_payload(method="ratio"))
    assert round(percent["lye_adjusted_g"], 3) == round(concentration["lye_adjusted_g"], 3)
    assert round(percent["lye_adjusted_g"], 3) == round(ratio["lye_adjusted_g"], 3)


def test_compute_service_sheet_shows_fragrance_and_additives_when_present():
    result = SoapToolComputationService.calculate(_payload())
    html = result["export"]["sheet_html"]

    assert "Fragrance & Essential Oils" in html
    assert "Lavender EO" in html
    assert "Additives" in html
    assert "Sodium Lactate" in html


def test_compute_service_sheet_rolls_citric_lye_into_total_with_footnote():
    payload = _payload()
    payload["additives"]["citric_pct"] = 2.0

    result = SoapToolComputationService.calculate(payload)
    html = result["export"]["sheet_html"]
    csv_rows = result["export"]["csv_rows"]

    extra_lye = float(result["additives"]["citricLyeG"])
    assert extra_lye > 0

    base_lye = float(result["lye_adjusted_base_g"])
    total_lye = float(result["lye_adjusted_g"])
    assert round(base_lye + extra_lye, 3) == round(total_lye, 3)

    expected_total_lye = round(total_lye, 2)
    lye_rows = [row for row in csv_rows if row[0] == "Lye"]
    assert len(lye_rows) == 1
    assert lye_rows[0][1].endswith("*")
    assert round(float(lye_rows[0][2]), 2) == expected_total_lye
    assert any(
        row[0] == "Notes" and "lye added extra to accommodate the extra citrus" in str(row[1])
        for row in csv_rows
    )

    assert "Sodium Hydroxide (NaOH)*" in html
    assert f"{expected_total_lye} g*" in html
    assert "lye added extra to accommodate the extra citrus." in html


def test_citric_extra_lye_recalculates_water_for_concentration_method():
    payload = _payload(method="concentration")
    payload["water"]["lye_concentration"] = 20
    payload["additives"]["citric_pct"] = 2.0

    result = SoapToolComputationService.calculate(payload)
    total_lye = float(result["lye_adjusted_g"])
    expected_water = total_lye * ((100 - 20) / 20)

    assert round(float(result["water_g"]), 3) == round(expected_water, 3)
    assert round(float(result["lye_concentration_pct"]), 3) == 20.0


def test_citric_extra_lye_uses_lye_type_multiplier():
    naoh_payload = _payload()
    naoh_payload["additives"]["citric_pct"] = 2.0
    naoh_result = SoapToolComputationService.calculate(naoh_payload)
    citric_g = float(naoh_result["additives"]["citricG"])
    assert round(float(naoh_result["additives"]["citricLyeG"]), 3) == round(citric_g * 0.624, 3)
    assert "0.624 x citric acid because NaOH was selected." in naoh_result["export"]["sheet_html"]

    koh_payload = _payload()
    koh_payload["lye"]["selected"] = "KOH"
    koh_payload["additives"]["citric_pct"] = 2.0
    koh_result = SoapToolComputationService.calculate(koh_payload)
    koh_citric_g = float(koh_result["additives"]["citricG"])
    assert round(float(koh_result["additives"]["citricLyeG"]), 3) == round(koh_citric_g * 0.71, 3)
    assert "Assumptions" in koh_result["export"]["sheet_html"]
    assert "0.71 x citric acid because KOH was selected." in koh_result["export"]["sheet_html"]
    assert any(
        row[0] == "Notes" and "0.71 x citric acid because KOH was selected." in str(row[1])
        for row in koh_result["export"]["csv_rows"]
    )


def test_quality_nudge_returns_adjusted_rows():
    payload = _payload()
    result = run_quality_nudge(
        {
            "oils": payload["oils"],
            "targets": {"hardness": 45, "cleansing": 14, "conditioning": 55, "bubbly": 26, "creamy": 24},
            "target_oils_g": 650,
        }
    )
    assert result["ok"] is True
    rows = result.get("adjusted_rows") or []
    assert rows
    assert all(float(row.get("grams") or 0) > 0 for row in rows)

