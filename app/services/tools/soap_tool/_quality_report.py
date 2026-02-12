"""Quality report compilation for soap tool results.

Synopsis:
Builds quality metrics, warning flags, and visual guidance from oils, water, and
additive outputs for the soap calculator display layer.

Glossary:
- Quality report: Structured bundle used by bars, warning cards, and guidance.
"""

from __future__ import annotations

from ._fatty_acids import compute_fatty_acids, compute_iodine, compute_qualities, compute_sat_unsat
from .types import SoapToolOilInput, _to_float

QUALITY_RANGES = {
    "hardness": (29.0, 54.0),
    "cleansing": (12.0, 22.0),
    "conditioning": (44.0, 69.0),
    "bubbly": (14.0, 46.0),
    "creamy": (16.0, 48.0),
}
IODINE_RANGE = (41.0, 70.0)
INS_RANGE = (136.0, 170.0)


# --- Quality warnings builder ---
# Purpose: Build warning strings based on quality and process thresholds.
# Inputs: Computed quality metrics and calculation context.
# Outputs: Ordered warning string list.
def _build_warnings(
    qualities: dict,
    fatty_pct: dict,
    iodine: float,
    ins: float,
    superfat: float,
    lye_concentration: float,
    additives: dict,
    oils: tuple[SoapToolOilInput, ...],
    total_oils: float,
    coverage_pct: float,
) -> list[str]:
    warnings: list[str] = []
    pufa = _to_float(fatty_pct.get("linoleic"), 0.0) + _to_float(fatty_pct.get("linolenic"), 0.0)
    lauric_myristic = _to_float(fatty_pct.get("lauric"), 0.0) + _to_float(fatty_pct.get("myristic"), 0.0)

    if iodine > IODINE_RANGE[1]:
        warnings.append("High iodine value can mean softer bars or faster rancidity.")
    if ins > 0 and ins < INS_RANGE[0]:
        warnings.append("INS is low (below 136); bars may be soft or have shorter shelf life.")
    if ins > INS_RANGE[1]:
        warnings.append("INS is high; bars may be brittle or overly cleansing.")
    if coverage_pct > 0 and pufa > 15:
        warnings.append("High linoleic/linolenic (PUFA) increases DOS risk; consider antioxidant or more stable oils.")
    if coverage_pct > 0 and _to_float(qualities.get("hardness"), 0.0) < QUALITY_RANGES["hardness"][0]:
        warnings.append("Hardness looks low; bars may be soft or slow to unmold.")
    if coverage_pct > 0 and _to_float(qualities.get("cleansing"), 0.0) > QUALITY_RANGES["cleansing"][1]:
        warnings.append("Cleansing is high; consider more conditioning oils.")
    if coverage_pct > 0 and _to_float(qualities.get("bubbly"), 0.0) < QUALITY_RANGES["bubbly"][0]:
        warnings.append("Bubbly lather is low; add 5-10% castor or coconut for more foam.")
    if coverage_pct > 0 and lauric_myristic > 35:
        warnings.append("High lauric/myristic can be drying or crumbly; cut warm and keep superfat at least 5%.")
    if superfat >= 15:
        warnings.append("Superfat is high (15%+); bars can be softer/greasy and may have shorter shelf life.")
    if lye_concentration > 0 and lye_concentration < 27:
        warnings.append("Very high water: slower trace and more shrinkage/ash.")
    if lye_concentration > 40:
        warnings.append("Low water: faster trace and more heat. Work quickly and avoid overheating.")
    if _to_float(additives.get("fragrancePct"), 0.0) > 3:
        warnings.append("Fragrance load above 3% can accelerate trace; follow supplier usage rates.")
    if _to_float(additives.get("citricPct"), 0.0) > 0:
        warnings.append("Citric acid consumes lye; extra lye has been added.")

    positive_oils = [oil for oil in oils if oil.grams > 0]
    if total_oils > 0 and len(positive_oils) == 1:
        warnings.append("Single-oil recipe; consider blending for balanced hardness, cleansing, and longevity.")
    if total_oils > 0 and len(positive_oils) > 1:
        max_share = max((oil.grams / total_oils) * 100.0 for oil in positive_oils)
        if max_share >= 90:
            warnings.append("One oil is over 90% of the formula; consider blending for balance.")

    return warnings


# --- Visual guidance builder ---
# Purpose: Build visual/behavior process tips from concentration and additives.
# Inputs: Fatty-acid percentages, concentration, and additive outputs.
# Outputs: Ordered tip string list.
def _build_visual_guidance(fatty_pct: dict, lye_concentration: float, additives: dict) -> list[str]:
    tips: list[str] = []
    lauric_myristic = _to_float(fatty_pct.get("lauric"), 0.0) + _to_float(fatty_pct.get("myristic"), 0.0)
    if lye_concentration > 0 and lye_concentration < 28:
        tips.append("High water can cause soda ash, warping, or glycerin rivers; keep temperatures even.")
    if lye_concentration > 40:
        tips.append("Low water (strong lye) can overheat or crack; soap cooler and watch for overheating.")
    if _to_float(additives.get("sugarPct"), 0.0) > 1:
        tips.append("Sugars add heat; soap cooler to avoid cracking or glycerin rivers.")
    if _to_float(additives.get("saltPct"), 0.0) > 1:
        tips.append("Salt can make bars brittle; cut sooner than usual.")
    if lauric_myristic > 35:
        tips.append("High lauric oils can crumble if cut cold; cut warm for cleaner edges.")
    if not tips:
        tips.append("No visual flags detected for this formula.")
    return tips


# --- Quality report compiler ---
# Purpose: Compute the full quality report bundle from calculator context.
# Inputs: Oils, totals, SAP average, superfat, water data, and additive outputs.
# Outputs: Structured quality report dictionary.
def build_quality_report(
    oils: tuple[SoapToolOilInput, ...],
    total_oils: float,
    sap_avg: float,
    superfat: float,
    water_data: dict,
    additives: dict,
) -> dict:
    iodine_data = compute_iodine(oils)
    fatty_data = compute_fatty_acids(oils)
    fatty_pct = fatty_data["fatty_acids_pct"]
    qualities = compute_qualities(fatty_pct)
    sat_unsat = compute_sat_unsat(fatty_pct)
    iodine = _to_float(iodine_data.get("iodine"), 0.0)
    ins = (sap_avg - iodine) if sap_avg and iodine else 0.0
    coverage_pct = (fatty_data["coverage_weight"] / total_oils) * 100.0 if total_oils > 0 else 0.0
    lye_concentration = _to_float(water_data.get("lye_concentration_pct"), 0.0)

    warnings = _build_warnings(
        qualities=qualities,
        fatty_pct=fatty_pct,
        iodine=iodine,
        ins=ins,
        superfat=superfat,
        lye_concentration=lye_concentration,
        additives=additives,
        oils=oils,
        total_oils=total_oils,
        coverage_pct=coverage_pct,
    )
    visual_guidance = _build_visual_guidance(
        fatty_pct=fatty_pct,
        lye_concentration=lye_concentration,
        additives=additives,
    )

    return {
        "qualities": qualities,
        "fatty_acids_pct": fatty_pct,
        "coverage_pct": coverage_pct,
        "iodine": iodine,
        "ins": ins,
        "sap_avg_koh": sap_avg,
        "sat_unsat": sat_unsat,
        "warnings": warnings,
        "visual_guidance": visual_guidance,
    }


__all__ = ["build_quality_report"]

