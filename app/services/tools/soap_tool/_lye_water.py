"""Soap lye/water bridge for full soap tool computation.

Synopsis:
Delegates canonical lye/water math to the existing soap calculator service and
returns normalized dictionary output for orchestration.

Glossary:
- Canonical lye/water: Existing service authority for soap lye and water values.
"""

from __future__ import annotations

from app.services.tools.soap_calculator import SoapToolCalculatorService

from .types import SoapToolComputeRequest


# --- Lye/water computation bridge ---
# Purpose: Reuse canonical soap calculator for lye and water values.
# Inputs: Full soap compute request object.
# Outputs: Dictionary payload from SoapToolCalculatorService.
def compute_lye_water(request: SoapToolComputeRequest) -> dict:
    payload = {
        "oils": [
            {
                "grams": oil.grams,
                "sap_koh": oil.sap_koh,
            }
            for oil in request.oils
        ],
        "lye": {
            "selected": request.lye.selected,
            "superfat": request.lye.superfat,
            "purity": request.lye.purity,
        },
        "water": {
            "method": request.water.method,
            "water_pct": request.water.water_pct,
            "lye_concentration": request.water.lye_concentration,
            "water_ratio": request.water.water_ratio,
        },
    }
    result = SoapToolCalculatorService.calculate(payload)
    return result.to_dict()


__all__ = ["compute_lye_water"]

