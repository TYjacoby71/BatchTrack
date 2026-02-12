"""Fatty-acid and quality metric computations for soap tool.

Synopsis:
Provides deterministic iodine, fatty-acid percentage, and soap quality metric
calculations from normalized oil input rows.

Glossary:
- Fatty profile: Per-oil fatty-acid percentage composition mapping.
"""

from __future__ import annotations

from .types import SoapToolOilInput, _to_float


# --- Iodine computation ---
# Purpose: Compute weighted iodine and coverage weight from oil inputs.
# Inputs: Normalized oil rows.
# Outputs: Dictionary with iodine value and covered weight in grams.
def compute_iodine(oils: tuple[SoapToolOilInput, ...]) -> dict:
    total_weight = 0.0
    weighted = 0.0
    for oil in oils:
        iodine = _to_float(oil.iodine, 0.0)
        grams = _to_float(oil.grams, 0.0)
        if iodine > 0 and grams > 0:
            total_weight += grams
            weighted += iodine * grams
    return {
        "iodine": (weighted / total_weight) if total_weight > 0 else 0.0,
        "coverage_weight": total_weight,
    }


# --- Fatty-acid aggregation ---
# Purpose: Compute weighted fatty-acid percentages across oil inputs.
# Inputs: Normalized oil rows.
# Outputs: Dictionary with fatty_acids percent map and coverage weight.
def compute_fatty_acids(oils: tuple[SoapToolOilInput, ...]) -> dict:
    totals: dict[str, float] = {}
    covered_weight = 0.0
    for oil in oils:
        grams = _to_float(oil.grams, 0.0)
        profile = oil.fatty_profile if isinstance(oil.fatty_profile, dict) else {}
        if grams <= 0 or not profile:
            continue
        covered_weight += grams
        for key, pct in profile.items():
            value = _to_float(pct, 0.0)
            if value > 0:
                totals[key] = totals.get(key, 0.0) + (grams * (value / 100.0))

    percents: dict[str, float] = {}
    if covered_weight > 0:
        for key, grams in totals.items():
            percents[key] = (grams / covered_weight) * 100.0

    return {
        "fatty_acids_pct": percents,
        "coverage_weight": covered_weight,
    }


# --- Soap quality metrics ---
# Purpose: Compute standard soap quality metrics from fatty-acid percentages.
# Inputs: Fatty-acid percentage mapping.
# Outputs: Quality metric dictionary.
def compute_qualities(fatty_acids_pct: dict[str, float]) -> dict:
    get = lambda key: _to_float(fatty_acids_pct.get(key), 0.0)
    return {
        "hardness": get("lauric") + get("myristic") + get("palmitic") + get("stearic"),
        "cleansing": get("lauric") + get("myristic"),
        "conditioning": get("oleic") + get("linoleic") + get("linolenic") + get("ricinoleic"),
        "bubbly": get("lauric") + get("myristic") + get("ricinoleic"),
        "creamy": get("palmitic") + get("stearic") + get("ricinoleic"),
    }


# --- Saturated/unsaturated split ---
# Purpose: Compute total saturated vs unsaturated fatty-acid percentages.
# Inputs: Fatty-acid percentage mapping.
# Outputs: Dictionary with saturated and unsaturated totals.
def compute_sat_unsat(fatty_acids_pct: dict[str, float]) -> dict:
    saturated = (
        _to_float(fatty_acids_pct.get("lauric"), 0.0)
        + _to_float(fatty_acids_pct.get("myristic"), 0.0)
        + _to_float(fatty_acids_pct.get("palmitic"), 0.0)
        + _to_float(fatty_acids_pct.get("stearic"), 0.0)
    )
    unsaturated = (
        _to_float(fatty_acids_pct.get("ricinoleic"), 0.0)
        + _to_float(fatty_acids_pct.get("oleic"), 0.0)
        + _to_float(fatty_acids_pct.get("linoleic"), 0.0)
        + _to_float(fatty_acids_pct.get("linolenic"), 0.0)
    )
    return {
        "saturated": saturated,
        "unsaturated": unsaturated,
    }


__all__ = [
    "compute_iodine",
    "compute_fatty_acids",
    "compute_qualities",
    "compute_sat_unsat",
]

