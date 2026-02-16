"""Soap advisory helpers for blend tips and quality-target nudging.

Synopsis:
Provides backend-owned advisory logic that was previously in frontend JS,
including oil blend behavior tips and quality-target nudge calculations.

Glossary:
- Quality nudge: Algorithmic oil redistribution toward selected quality targets.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from ._fatty_acids import compute_fatty_acids, compute_qualities
from ._policy import OIL_TIP_RULES
from .types import SoapToolOilInput, _clamp, _to_float

_QUALITY_KEYS = ("hardness", "cleansing", "conditioning", "bubbly", "creamy")
_NUDGE_STRENGTH = 0.8

_COMPILED_OIL_TIP_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(
            str(rule.get("pattern") or ""),
            re.IGNORECASE if "i" in str(rule.get("flags") or "").lower() else 0,
        ),
        str(rule.get("tip") or "").strip(),
    )
    for rule in OIL_TIP_RULES
    if str(rule.get("pattern") or "").strip() and str(rule.get("tip") or "").strip()
)


# --- Unique list append helper ---
# Purpose: Append a string once while preserving insertion order.
# Inputs: Mutable output list, seen-set, and candidate text.
# Outputs: None (mutates outputs in place).
def _append_once(items: list[str], seen: set[str], value: str) -> None:
    cleaned = value.strip()
    if not cleaned or cleaned in seen:
        return
    seen.add(cleaned)
    items.append(cleaned)


# --- Oil quality score calculator ---
# Purpose: Convert one fatty-profile map into normalized quality scoring components.
# Inputs: Fatty-acid profile mapping.
# Outputs: Dict with normalized hardness/cleansing/conditioning/bubbly/creamy scores.
def _compute_oil_quality_scores(fatty_profile: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(fatty_profile, Mapping):
        return {key: 0.0 for key in _QUALITY_KEYS}
    profile = {
        "lauric": _to_float(fatty_profile.get("lauric"), 0.0),
        "myristic": _to_float(fatty_profile.get("myristic"), 0.0),
        "palmitic": _to_float(fatty_profile.get("palmitic"), 0.0),
        "stearic": _to_float(fatty_profile.get("stearic"), 0.0),
        "ricinoleic": _to_float(fatty_profile.get("ricinoleic"), 0.0),
        "oleic": _to_float(fatty_profile.get("oleic"), 0.0),
        "linoleic": _to_float(fatty_profile.get("linoleic"), 0.0),
        "linolenic": _to_float(fatty_profile.get("linolenic"), 0.0),
    }
    qualities = compute_qualities(profile)
    return {
        "hardness": _to_float(qualities.get("hardness"), 0.0) / 100.0,
        "cleansing": _to_float(qualities.get("cleansing"), 0.0) / 100.0,
        "conditioning": _to_float(qualities.get("conditioning"), 0.0) / 100.0,
        "bubbly": _to_float(qualities.get("bubbly"), 0.0) / 100.0,
        "creamy": _to_float(qualities.get("creamy"), 0.0) / 100.0,
    }


# --- Oil blend tips compiler ---
# Purpose: Build blend-behavior tips from oil names and fatty profile thresholds.
# Inputs: Tuple of normalized oil inputs.
# Outputs: Ordered tip list capped to six entries.
def build_oil_blend_tips(oils: tuple[SoapToolOilInput, ...]) -> list[str]:
    tips: list[str] = []
    seen: set[str] = set()
    for oil in oils:
        grams = _to_float(oil.grams, 0.0)
        if grams <= 0:
            continue
        display_name = (oil.name or "").strip() or "This oil"
        lower_name = display_name.lower()
        for pattern, tip in _COMPILED_OIL_TIP_RULES:
            if pattern.search(lower_name):
                _append_once(tips, seen, tip)
        profile = oil.fatty_profile if isinstance(oil.fatty_profile, Mapping) else {}
        if not profile:
            continue
        lauric = _to_float(profile.get("lauric"), 0.0)
        myristic = _to_float(profile.get("myristic"), 0.0)
        palmitic = _to_float(profile.get("palmitic"), 0.0)
        stearic = _to_float(profile.get("stearic"), 0.0)
        ricinoleic = _to_float(profile.get("ricinoleic"), 0.0)
        oleic = _to_float(profile.get("oleic"), 0.0)
        linoleic = _to_float(profile.get("linoleic"), 0.0)
        linolenic = _to_float(profile.get("linolenic"), 0.0)
        if (lauric + myristic) >= 30:
            _append_once(
                tips,
                seen,
                f"{display_name} is high in lauric/myristic; expect faster trace and stronger cleansing.",
            )
        if (palmitic + stearic) >= 40:
            _append_once(
                tips,
                seen,
                f"{display_name} is high in palmitic/stearic; expect a harder bar and quicker set-up.",
            )
        if oleic >= 60:
            _append_once(tips, seen, f"{display_name} is high oleic; trace may be slow and bars may start softer.")
        if (linoleic + linolenic) >= 20:
            _append_once(tips, seen, f"{display_name} is high in PUFAs; keep the % lower to reduce DOS risk.")
        if ricinoleic >= 60:
            _append_once(tips, seen, f"{display_name} boosts lather but can feel tacky; keep under 10-15%.")
        if len(tips) >= 6:
            break
    return tips[:6]


# --- Quality-target nudge runner ---
# Purpose: Rebalance oil grams toward selected quality targets using backend rules.
# Inputs: Request payload containing oils, quality targets, and optional target oils total.
# Outputs: Result dict with ok/error status, warnings, and adjusted rows.
def run_quality_nudge(payload: Mapping[str, Any] | None) -> dict:
    data = payload if isinstance(payload, Mapping) else {}
    oils_raw = data.get("oils")
    targets_raw = data.get("targets")
    oils_list = oils_raw if isinstance(oils_raw, list) else []
    targets_map = targets_raw if isinstance(targets_raw, Mapping) else {}

    targets = {
        key: _to_float(targets_map.get(key), 0.0)
        for key in _QUALITY_KEYS
        if key in targets_map
    }
    if not targets:
        return {
            "ok": False,
            "error": "Select a quality target to nudge the blend.",
            "warnings": [],
            "adjusted_rows": [],
        }

    indexed_oils: list[tuple[int, SoapToolOilInput]] = []
    for index, row in enumerate(oils_list):
        if not isinstance(row, Mapping):
            continue
        oil = SoapToolOilInput.from_payload(row)
        if oil.grams > 0:
            row_index = row.get("row_index")
            try:
                output_index = int(row_index) if row_index not in (None, "", []) else index
            except (TypeError, ValueError):
                output_index = index
            indexed_oils.append((output_index, oil))

    if not indexed_oils:
        return {
            "ok": False,
            "error": "Add oils before nudging toward a target.",
            "warnings": [],
            "adjusted_rows": [],
        }

    warnings: list[str] = []
    missing_fatty = sum(
        1 for _index, oil in indexed_oils if not isinstance(oil.fatty_profile, Mapping) or not oil.fatty_profile
    )
    if missing_fatty == len(indexed_oils):
        return {
            "ok": False,
            "error": "None of the selected oils have fatty acid data, so targets cannot be applied.",
            "warnings": [],
            "adjusted_rows": [],
        }
    if missing_fatty:
        warnings.append("Some oils are missing fatty acid data. The nudge will only use oils with profiles.")

    oils_only = tuple(oil for _index, oil in indexed_oils)
    fatty = compute_fatty_acids(oils_only)
    current_qualities = compute_qualities(fatty.get("fatty_acids_pct") or {})
    deltas = {
        key: _clamp((targets[key] - _to_float(current_qualities.get(key), 0.0)) / 100.0, -1.0, 1.0)
        for key in _QUALITY_KEYS
        if key in targets
    }
    total_oils = sum(_to_float(oil.grams, 0.0) for _index, oil in indexed_oils)

    adjusted_raw: list[tuple[int, float]] = []
    total_adjusted = 0.0
    for index, oil in indexed_oils:
        scores = _compute_oil_quality_scores(oil.fatty_profile)
        adjustment = (
            (deltas.get("hardness", 0.0) * scores["hardness"])
            + (deltas.get("cleansing", 0.0) * scores["cleansing"])
            + (deltas.get("conditioning", 0.0) * scores["conditioning"])
            + (deltas.get("bubbly", 0.0) * scores["bubbly"])
            + (deltas.get("creamy", 0.0) * scores["creamy"])
        )
        factor = _clamp(1.0 + (adjustment * _NUDGE_STRENGTH), 0.2, 1.8)
        next_grams = _to_float(oil.grams, 0.0) * factor
        adjusted_raw.append((index, next_grams))
        total_adjusted += next_grams

    if total_adjusted <= 0:
        return {
            "ok": False,
            "error": "Unable to adjust blend with current data.",
            "warnings": warnings,
            "adjusted_rows": [],
        }

    scale = (total_oils / total_adjusted) if total_adjusted > 0 else 1.0
    target_oils_g = _to_float(data.get("target_oils_g"), 0.0)
    target_for_pct = target_oils_g if target_oils_g > 0 else total_oils
    adjusted_rows = []
    for index, grams in adjusted_raw:
        scaled_grams = grams * scale
        pct = (scaled_grams / target_for_pct) * 100.0 if target_for_pct > 0 else 0.0
        adjusted_rows.append(
            {
                "index": index,
                "grams": scaled_grams,
                "pct": pct,
            }
        )

    return {
        "ok": True,
        "warnings": warnings,
        "message": "Blend nudged toward selected targets. Re-check results and adjust as needed.",
        "adjusted_rows": adjusted_rows,
    }


__all__ = [
    "build_oil_blend_tips",
    "run_quality_nudge",
]
