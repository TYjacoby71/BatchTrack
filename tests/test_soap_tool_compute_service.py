from app.services.tools.soap_tool import SoapToolComputationService


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
    assert "export" in result
    assert isinstance(result["export"]["csv_rows"], list)
    assert "<html" in result["export"]["sheet_html"].lower()


def test_compute_service_lye_is_method_independent():
    percent = SoapToolComputationService.calculate(_payload(method="percent"))
    concentration = SoapToolComputationService.calculate(_payload(method="concentration"))
    ratio = SoapToolComputationService.calculate(_payload(method="ratio"))
    assert round(percent["lye_adjusted_g"], 3) == round(concentration["lye_adjusted_g"], 3)
    assert round(percent["lye_adjusted_g"], 3) == round(ratio["lye_adjusted_g"], 3)

