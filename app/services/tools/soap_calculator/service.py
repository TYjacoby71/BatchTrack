"""Core soap calculator service for the public soap tool.

Synopsis:
Provides a compatibility wrapper for lye/water outputs while delegating core
math authority to the consolidated soap tool service package.

Glossary:
- Lye selected: UI selection including the special "KOH90" purity-lock option.
- Lye type: Chemical family used in SAP conversion (NaOH or KOH).
- Water method:
  - percent: Water as % of oils.
  - concentration: Lye concentration percentage.
  - ratio: Water-to-lye ratio.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.services.tools.soap_tool._lye_water import compute_lye_water_values

from .types import SoapCalculationRequest, SoapCalculationResult


# --- Soap tool calculator service ---
# Purpose: Provide deterministic lye/water calculations for soap tool requests.
# Inputs: Structured soap calculation payload/request objects.
# Outputs: Typed SoapCalculationResult used by API and UI orchestration.
class SoapToolCalculatorService:
    """Compatibility calculator exposing legacy lye/water result shape."""

    @classmethod
    def calculate(cls, payload: Mapping[str, Any] | None) -> SoapCalculationResult:
        """Calculate lye and water outputs from tool payload data."""
        request = SoapCalculationRequest.from_payload(payload or {})
        return cls.calculate_from_request(request)

    @classmethod
    def calculate_from_request(cls, request: SoapCalculationRequest) -> SoapCalculationResult:
        values = compute_lye_water_values(
            oils=[
                {
                    "grams": oil.grams,
                    "sap_koh": oil.sap_koh,
                }
                for oil in request.oils
            ],
            selected=request.lye_selected,
            superfat_pct=request.superfat_pct,
            purity_pct=request.lye_purity_pct,
            water_method=request.water_method,
            water_pct=request.water_pct,
            lye_concentration_input_pct=request.lye_concentration_pct,
            water_ratio_input=request.water_ratio,
        )
        return SoapCalculationResult(**values)


__all__ = ["SoapToolCalculatorService"]

