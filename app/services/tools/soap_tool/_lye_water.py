"""Soap lye/water authority for full soap tool computation.

Synopsis:
Provides canonical lye/water calculations for soap tool orchestration and
legacy wrapper services.

Glossary:
- Canonical lye/water: Single authoritative lye and water computation path.
"""

from __future__ import annotations

from .types import SoapToolComputeRequest
from .types import _clamp

DEFAULT_WATER_PCT = 33.0
DEFAULT_LYE_CONCENTRATION = 33.0
DEFAULT_WATER_RATIO = 2.0
DEFAULT_NAOH_FALLBACK_PER_G = 0.138
DEFAULT_KOH_FALLBACK_PER_G = 0.194
NAOH_FACTOR_FROM_KOH_SAP = 0.713
SAP_KOH_DECIMAL_THRESHOLD = 1.0
SAP_KOH_DECIMAL_TO_MG_FACTOR = 1000.0


# --- SAP normalization ---
# Purpose: Normalize SAP KOH values from decimal or mg/g formats.
# Inputs: Raw SAP KOH numeric value.
# Outputs: SAP value in mg KOH per gram oil.
def normalize_sap_koh(sap_koh: float) -> float:
    normalized = max(0.0, float(sap_koh))
    if 0.0 < normalized <= SAP_KOH_DECIMAL_THRESHOLD:
        return normalized * SAP_KOH_DECIMAL_TO_MG_FACTOR
    return normalized


# --- Lye/water primitive calculator ---
# Purpose: Compute canonical lye/water values from primitive soap inputs.
# Inputs: Oils list and lye/water settings.
# Outputs: Dictionary mirroring soap lye/water result fields.
def compute_lye_water_values(
    *,
    oils: list[dict],
    selected: str,
    superfat_pct: float,
    purity_pct: float,
    water_method: str,
    water_pct: float,
    lye_concentration_input_pct: float,
    water_ratio_input: float,
) -> dict:
    selected_upper = (selected or "NaOH").upper()
    if selected_upper not in {"NAOH", "KOH", "KOH90"}:
        selected_upper = "NAOH"
    lye_type = "KOH" if selected_upper in {"KOH", "KOH90"} else "NaOH"
    superfat = _clamp(float(superfat_pct), 0.0, 20.0)
    purity = _clamp(float(purity_pct), 90.0, 100.0)
    if selected_upper == "KOH90":
        purity = 90.0

    method = (water_method or "percent").strip().lower()
    if method not in {"percent", "concentration", "ratio"}:
        method = "percent"

    water_pct_sanitized = float(water_pct) if float(water_pct) > 0 else DEFAULT_WATER_PCT
    lye_conc_input = float(lye_concentration_input_pct) if float(lye_concentration_input_pct) > 0 else DEFAULT_LYE_CONCENTRATION
    lye_conc_input = _clamp(lye_conc_input, 20.0, 50.0)
    ratio_input = float(water_ratio_input) if float(water_ratio_input) > 0 else DEFAULT_WATER_RATIO
    ratio_input = _clamp(ratio_input, 1.0, 4.0)

    total_oils = sum(max(0.0, float(row.get("grams") or 0.0)) for row in oils)
    lye_total = 0.0
    sap_weighted = 0.0
    sap_weight_g = 0.0
    for row in oils:
        grams = max(0.0, float(row.get("grams") or 0.0))
        sap_koh = normalize_sap_koh(float(row.get("sap_koh") or 0.0))
        if grams <= 0 or sap_koh <= 0:
            continue
        per_g = (sap_koh / 1000.0) if lye_type == "KOH" else ((sap_koh * NAOH_FACTOR_FROM_KOH_SAP) / 1000.0)
        lye_total += grams * per_g
        sap_weighted += sap_koh * grams
        sap_weight_g += grams

    sap_avg = (sap_weighted / sap_weight_g) if sap_weight_g > 0 else 0.0
    used_sap_fallback = lye_total <= 0 and total_oils > 0
    if used_sap_fallback:
        fallback_per_g = DEFAULT_KOH_FALLBACK_PER_G if lye_type == "KOH" else DEFAULT_NAOH_FALLBACK_PER_G
        lye_total = total_oils * fallback_per_g

    lye_pure = lye_total * (1.0 - (superfat / 100.0))
    lye_adjusted = lye_pure / (purity / 100.0) if purity > 0 else lye_pure

    if method == "percent":
        water_g = total_oils * (water_pct_sanitized / 100.0)
    elif method == "concentration":
        water_g = lye_adjusted * ((100.0 - lye_conc_input) / lye_conc_input) if (lye_adjusted > 0 and lye_conc_input > 0) else 0.0
    else:
        water_g = lye_adjusted * ratio_input if lye_adjusted > 0 else 0.0

    lye_concentration = (lye_adjusted / (lye_adjusted + water_g)) * 100.0 if (lye_adjusted + water_g) > 0 else 0.0
    water_lye_ratio = (water_g / lye_adjusted) if lye_adjusted > 0 else 0.0

    return {
        "total_oils_g": total_oils,
        "lye_type": lye_type,
        "lye_selected": selected_upper,
        "superfat_pct": superfat,
        "lye_purity_pct": purity,
        "lye_total_g": lye_total,
        "lye_pure_g": lye_pure,
        "lye_adjusted_g": lye_adjusted,
        "water_method": method,
        "water_pct": water_pct_sanitized,
        "lye_concentration_input_pct": lye_conc_input,
        "water_ratio_input": ratio_input,
        "water_g": water_g,
        "lye_concentration_pct": lye_concentration,
        "water_lye_ratio": water_lye_ratio,
        "sap_avg_koh": sap_avg,
        "used_sap_fallback": used_sap_fallback,
    }


# --- Lye/water computation bridge ---
# Purpose: Compute canonical soap lye and water values from a compute request.
# Inputs: Full soap compute request object.
# Outputs: Dictionary payload for orchestration.
def compute_lye_water(request: SoapToolComputeRequest) -> dict:
    return compute_lye_water_values(
        oils=[
            {
                "grams": oil.grams,
                "sap_koh": oil.sap_koh,
            }
            for oil in request.oils
        ],
        selected=request.lye.selected,
        superfat_pct=request.lye.superfat,
        purity_pct=request.lye.purity,
        water_method=request.water.method,
        water_pct=request.water.water_pct,
        lye_concentration_input_pct=request.water.lye_concentration,
        water_ratio_input=request.water.water_ratio,
    )


__all__ = [
    "compute_lye_water",
    "compute_lye_water_values",
    "normalize_sap_koh",
]

