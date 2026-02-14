"""Soap additive and fragrance computations.

Synopsis:
Calculates additive/fragrance grams, percentages, and citric-acid lye offset
from normalized stage payload values.

Glossary:
- Additives: Non-oil ingredients expressed as % of oils.
"""

from __future__ import annotations

from .types import SoapToolAdditivesInput, SoapToolFragranceInput, _clamp


# --- Fragrance row normalization ---
# Purpose: Normalize fragrance rows to grams + percent based on oils total.
# Inputs: Total oils and fragrance input rows.
# Outputs: Tuple of normalized fragrance dictionaries.
def normalize_fragrance_rows(
    total_oils_g: float,
    fragrances: tuple[SoapToolFragranceInput, ...],
) -> tuple[dict, ...]:
    rows: list[dict] = []
    for row in fragrances:
        grams = _clamp(float(row.grams), 0.0)
        pct = _clamp(float(row.pct), 0.0, 100.0)
        if grams <= 0 and pct > 0 and total_oils_g > 0:
            grams = total_oils_g * (pct / 100.0)
        if pct <= 0 and grams > 0 and total_oils_g > 0:
            pct = (grams / total_oils_g) * 100.0
        if grams <= 0 and pct <= 0:
            continue
        rows.append(
            {
                "name": row.name or "Fragrance/Essential Oils",
                "grams": grams,
                "pct": pct,
            }
        )
    return tuple(rows)


# --- Additives computation ---
# Purpose: Compute additive/fragrance outputs used by results and exports.
# Inputs: Oils total, lye type, additive settings, and fragrance rows.
# Outputs: Dictionary of additive output values.
def compute_additives(
    total_oils_g: float,
    lye_type: str,
    additive_settings: SoapToolAdditivesInput,
    fragrances: tuple[SoapToolFragranceInput, ...],
) -> dict:
    base_oils = _clamp(float(total_oils_g), 0.0)
    normalized_fragrances = normalize_fragrance_rows(base_oils, fragrances)
    fragrance_g = sum(row["grams"] for row in normalized_fragrances)
    fragrance_pct = sum(row["pct"] for row in normalized_fragrances)

    lactate_pct = _clamp(additive_settings.lactate_pct, 0.0, 100.0)
    sugar_pct = _clamp(additive_settings.sugar_pct, 0.0, 100.0)
    salt_pct = _clamp(additive_settings.salt_pct, 0.0, 100.0)
    citric_pct = _clamp(additive_settings.citric_pct, 0.0, 100.0)

    lactate_g = base_oils * (lactate_pct / 100.0)
    sugar_g = base_oils * (sugar_pct / 100.0)
    salt_g = base_oils * (salt_pct / 100.0)
    citric_g = base_oils * (citric_pct / 100.0)
    # Standard calculator multipliers for citric-acid neutralization.
    citric_factor = 0.71 if str(lye_type).upper() == "KOH" else 0.624
    citric_lye_g = citric_g * citric_factor

    return {
        "fragrancePct": fragrance_pct,
        "lactatePct": lactate_pct,
        "sugarPct": sugar_pct,
        "saltPct": salt_pct,
        "citricPct": citric_pct,
        "fragranceG": fragrance_g,
        "lactateG": lactate_g,
        "sugarG": sugar_g,
        "saltG": salt_g,
        "citricG": citric_g,
        "citricLyeG": citric_lye_g,
        "fragranceRows": list(normalized_fragrances),
        "lactateName": additive_settings.lactate_name,
        "sugarName": additive_settings.sugar_name,
        "saltName": additive_settings.salt_name,
        "citricName": additive_settings.citric_name,
    }


__all__ = [
    "compute_additives",
    "normalize_fragrance_rows",
]

