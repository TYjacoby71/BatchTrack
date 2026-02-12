"""Soap tool orchestration service.

Synopsis:
Compiles stage payloads into a single service-owned compute result that
includes lye/water, additives, quality data, card metrics, and export payloads.

Glossary:
- Orchestration: Consolidating stage outputs into one canonical response.
"""

from __future__ import annotations

from ._additives import compute_additives
from ._lye_water import compute_lye_water
from ._quality_report import build_quality_report
from ._sheet import build_formula_csv_rows, build_formula_csv_text, build_formula_sheet_html
from .types import SoapToolComputeRequest, _to_float


# --- Results card compiler ---
# Purpose: Build normalized card metrics from computed totals.
# Inputs: Lye/water result dict, additives dict, quality report dict, and oils total.
# Outputs: Result-card metric dictionary.
def _build_results_card(lye_water: dict, additives: dict, quality_report: dict, total_oils: float) -> dict:
    lye_adjusted = _to_float(lye_water.get("lye_adjusted_g"), 0.0)
    water_g = _to_float(lye_water.get("water_g"), 0.0)
    batch_yield = (
        total_oils
        + lye_adjusted
        + water_g
        + _to_float(additives.get("fragranceG"), 0.0)
        + _to_float(additives.get("lactateG"), 0.0)
        + _to_float(additives.get("sugarG"), 0.0)
        + _to_float(additives.get("saltG"), 0.0)
        + _to_float(additives.get("citricG"), 0.0)
    )
    sat_unsat = quality_report.get("sat_unsat") or {}
    sat = _to_float(sat_unsat.get("saturated"), 0.0)
    unsat = _to_float(sat_unsat.get("unsaturated"), 0.0)
    sat_unsat_label = f"{round(sat, 0)}:{round(unsat, 0)}" if (sat + unsat) > 0 else "--"
    return {
        "lye_adjusted_g": lye_adjusted,
        "water_g": water_g,
        "batch_yield_g": batch_yield,
        "lye_concentration_pct": _to_float(lye_water.get("lye_concentration_pct"), 0.0),
        "water_lye_ratio": _to_float(lye_water.get("water_lye_ratio"), 0.0),
        "total_oils_g": total_oils,
        "superfat_pct": _to_float(lye_water.get("superfat_pct"), 0.0),
        "sat_unsat_ratio_label": sat_unsat_label,
    }


# --- Soap tool computation orchestrator ---
# Purpose: Provide one canonical service entrypoint for soap tool outputs.
# Inputs: Raw soap tool payload mapping.
# Outputs: Dictionary payload consumed by soap tool UI.
class SoapToolComputationService:
    @classmethod
    def calculate(cls, payload: dict | None) -> dict:
        request = SoapToolComputeRequest.from_payload(payload or {})
        lye_water = compute_lye_water(request)
        total_oils = _to_float(lye_water.get("total_oils_g"), 0.0)
        additives = compute_additives(
            total_oils_g=total_oils,
            lye_type=str(lye_water.get("lye_type") or "NaOH"),
            additive_settings=request.additives,
            fragrances=request.fragrances,
        )
        quality_report = build_quality_report(
            oils=request.oils,
            total_oils=total_oils,
            sap_avg=_to_float(lye_water.get("sap_avg_koh"), 0.0),
            superfat=_to_float(lye_water.get("superfat_pct"), 0.0),
            water_data={
                "lye_concentration_pct": _to_float(lye_water.get("lye_concentration_pct"), 0.0),
                "water_lye_ratio": _to_float(lye_water.get("water_lye_ratio"), 0.0),
                "water_g": _to_float(lye_water.get("water_g"), 0.0),
            },
            additives=additives,
        )
        results_card = _build_results_card(
            lye_water=lye_water,
            additives=additives,
            quality_report=quality_report,
            total_oils=total_oils,
        )

        result: dict = dict(lye_water)
        result["oils"] = [
            {
                "name": oil.name,
                "grams": oil.grams,
                "sap_koh": oil.sap_koh,
                "iodine": oil.iodine,
                "fatty_profile": oil.fatty_profile,
                "global_item_id": oil.global_item_id,
                "default_unit": oil.default_unit,
                "ingredient_category_name": oil.ingredient_category_name,
            }
            for oil in request.oils
        ]
        result["fragrances"] = list(additives.get("fragranceRows") or [])
        result["additives"] = additives
        result["quality_report"] = quality_report
        result["results_card"] = results_card

        unit_display = request.meta.unit_display
        csv_rows = build_formula_csv_rows(result, unit_display)
        result["export"] = {
            "csv_rows": csv_rows,
            "csv_text": build_formula_csv_text(csv_rows),
            "sheet_html": build_formula_sheet_html(result, unit_display),
        }
        return result


__all__ = ["SoapToolComputationService"]

