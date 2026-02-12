"""Core soap calculator service for the public soap tool.

Synopsis:
Provides a structured, testable calculation pipeline for lye/water values.

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

from .types import SoapCalculationRequest, SoapCalculationResult, _clamp


class SoapToolCalculatorService:
    """Deterministic calculator for soap tool lye/water results."""

    DEFAULT_WATER_PCT = 33.0
    DEFAULT_LYE_CONCENTRATION = 33.0
    DEFAULT_WATER_RATIO = 2.0
    DEFAULT_NAOH_FALLBACK_PER_G = 0.138
    DEFAULT_KOH_FALLBACK_PER_G = 0.194
    NAOH_FACTOR_FROM_KOH_SAP = 0.713

    @classmethod
    def calculate(cls, payload: Mapping[str, Any] | None) -> SoapCalculationResult:
        """Calculate lye and water outputs from tool payload data."""
        request = SoapCalculationRequest.from_payload(payload or {})
        return cls.calculate_from_request(request)

    @classmethod
    def calculate_from_request(cls, request: SoapCalculationRequest) -> SoapCalculationResult:
        selected = (request.lye_selected or "NaOH").upper()
        if selected not in {"NAOH", "KOH", "KOH90"}:
            selected = "NAOH"

        lye_type = "KOH" if selected in {"KOH", "KOH90"} else "NaOH"
        superfat = _clamp(float(request.superfat_pct), 0.0, 20.0)
        purity = _clamp(float(request.lye_purity_pct), 90.0, 100.0)
        if selected == "KOH90":
            purity = 90.0

        method = (request.water_method or "percent").strip().lower()
        if method not in {"percent", "concentration", "ratio"}:
            method = "percent"

        water_pct = float(request.water_pct) if request.water_pct > 0 else cls.DEFAULT_WATER_PCT
        lye_concentration_input = (
            float(request.lye_concentration_pct)
            if request.lye_concentration_pct > 0
            else cls.DEFAULT_LYE_CONCENTRATION
        )
        lye_concentration_input = _clamp(lye_concentration_input, 20.0, 50.0)
        water_ratio_input = float(request.water_ratio) if request.water_ratio > 0 else cls.DEFAULT_WATER_RATIO
        water_ratio_input = _clamp(water_ratio_input, 1.0, 4.0)

        total_oils = sum(max(0.0, oil.grams) for oil in request.oils)

        lye_total = 0.0
        sap_weighted = 0.0
        sap_weight_g = 0.0
        for oil in request.oils:
            grams = max(0.0, oil.grams)
            sap_koh = max(0.0, oil.sap_koh)
            if grams <= 0 or sap_koh <= 0:
                continue
            per_g = (
                sap_koh / 1000.0
                if lye_type == "KOH"
                else (sap_koh * cls.NAOH_FACTOR_FROM_KOH_SAP) / 1000.0
            )
            lye_total += grams * per_g
            sap_weighted += sap_koh * grams
            sap_weight_g += grams

        sap_avg = (sap_weighted / sap_weight_g) if sap_weight_g > 0 else 0.0
        used_sap_fallback = lye_total <= 0 and total_oils > 0
        if used_sap_fallback:
            fallback_per_g = (
                cls.DEFAULT_KOH_FALLBACK_PER_G
                if lye_type == "KOH"
                else cls.DEFAULT_NAOH_FALLBACK_PER_G
            )
            lye_total = total_oils * fallback_per_g

        lye_pure = lye_total * (1.0 - (superfat / 100.0))
        lye_adjusted = lye_pure / (purity / 100.0) if purity > 0 else lye_pure

        water_g = 0.0
        if method == "percent":
            # Percent mode is anchored to oils total, independent of lye amount.
            water_g = total_oils * (water_pct / 100.0)
        elif method == "concentration":
            water_g = (
                lye_adjusted * ((100.0 - lye_concentration_input) / lye_concentration_input)
                if lye_adjusted > 0 and lye_concentration_input > 0
                else 0.0
            )
        elif method == "ratio":
            water_g = (lye_adjusted * water_ratio_input) if lye_adjusted > 0 else 0.0

        lye_concentration = (
            (lye_adjusted / (lye_adjusted + water_g)) * 100.0
            if (lye_adjusted + water_g) > 0
            else 0.0
        )
        water_lye_ratio = (water_g / lye_adjusted) if lye_adjusted > 0 else 0.0

        return SoapCalculationResult(
            total_oils_g=total_oils,
            lye_type=lye_type,
            lye_selected=selected,
            superfat_pct=superfat,
            lye_purity_pct=purity,
            lye_total_g=lye_total,
            lye_pure_g=lye_pure,
            lye_adjusted_g=lye_adjusted,
            water_method=method,
            water_pct=water_pct,
            lye_concentration_input_pct=lye_concentration_input,
            water_ratio_input=water_ratio_input,
            water_g=water_g,
            lye_concentration_pct=lye_concentration,
            water_lye_ratio=water_lye_ratio,
            sap_avg_koh=sap_avg,
            used_sap_fallback=used_sap_fallback,
        )


__all__ = ["SoapToolCalculatorService"]

