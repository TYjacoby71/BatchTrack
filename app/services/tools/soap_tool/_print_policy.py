"""Canonical print-fill policy for soap sheet exports.

Synopsis:
Defines mold-fill thresholds and guidance metadata used by both backend
normalization and frontend confirmation UX.

Glossary:
- Fill %: Final batch yield divided by effective mold capacity.
"""

from __future__ import annotations

from typing import Any

PRINT_CONFIRM_MIN_FILL_PCT = 90.0
PRINT_CONFIRM_MAX_FILL_PCT = 120.0
PRINT_CONFIRM_STRONG_LOW_FILL_PCT = 80.0
PRINT_CONFIRM_STRONG_HIGH_FILL_PCT = 130.0
PRINT_NORMALIZE_MIN_PCT = 50.0
PRINT_NORMALIZE_MAX_PCT = 200.0

PRINT_FILL_GUIDANCE = {
    "strong_low": {
        "toneClass": "text-danger",
        "messageClass": "alert-danger",
        "message": "This recipe is far below mold capacity and may underfill bars.",
    },
    "low": {
        "toneClass": "text-warning",
        "messageClass": "alert-warning",
        "message": "This recipe is below your target range and may leave extra headspace.",
    },
    "high": {
        "toneClass": "text-warning",
        "messageClass": "alert-warning",
        "message": "This recipe is above your target range and may overflow this mold.",
    },
    "strong_high": {
        "toneClass": "text-danger",
        "messageClass": "alert-danger",
        "message": "This recipe is far above mold capacity and has a high overflow risk.",
    },
    "ok": {
        "toneClass": "text-success",
        "messageClass": "alert-success",
        "message": "This recipe is inside your target fill range.",
    },
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if cleaned == "":
                return float(default)
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def clamp_print_target_pct(value: Any) -> float:
    raw = _to_float(value, 100.0)
    if raw <= 0:
        raw = 100.0
    if raw < PRINT_NORMALIZE_MIN_PCT:
        return PRINT_NORMALIZE_MIN_PCT
    if raw > PRINT_NORMALIZE_MAX_PCT:
        return PRINT_NORMALIZE_MAX_PCT
    return raw


def get_print_fill_guidance(fill_pct: Any) -> dict[str, str]:
    pct = _to_float(fill_pct, 0.0)
    if pct < PRINT_CONFIRM_MIN_FILL_PCT:
        if pct < PRINT_CONFIRM_STRONG_LOW_FILL_PCT:
            return dict(PRINT_FILL_GUIDANCE["strong_low"])
        return dict(PRINT_FILL_GUIDANCE["low"])
    if pct > PRINT_CONFIRM_MAX_FILL_PCT:
        if pct > PRINT_CONFIRM_STRONG_HIGH_FILL_PCT:
            return dict(PRINT_FILL_GUIDANCE["strong_high"])
        return dict(PRINT_FILL_GUIDANCE["high"])
    return dict(PRINT_FILL_GUIDANCE["ok"])


def get_print_policy() -> dict:
    return {
        "confirmMinPct": PRINT_CONFIRM_MIN_FILL_PCT,
        "confirmMaxPct": PRINT_CONFIRM_MAX_FILL_PCT,
        "strongLowPct": PRINT_CONFIRM_STRONG_LOW_FILL_PCT,
        "strongHighPct": PRINT_CONFIRM_STRONG_HIGH_FILL_PCT,
        "normalizeMinPct": PRINT_NORMALIZE_MIN_PCT,
        "normalizeMaxPct": PRINT_NORMALIZE_MAX_PCT,
        "guidance": {key: dict(value) for key, value in PRINT_FILL_GUIDANCE.items()},
    }


__all__ = [
    "PRINT_CONFIRM_MIN_FILL_PCT",
    "PRINT_CONFIRM_MAX_FILL_PCT",
    "PRINT_CONFIRM_STRONG_LOW_FILL_PCT",
    "PRINT_CONFIRM_STRONG_HIGH_FILL_PCT",
    "PRINT_NORMALIZE_MIN_PCT",
    "PRINT_NORMALIZE_MAX_PCT",
    "clamp_print_target_pct",
    "get_print_fill_guidance",
    "get_print_policy",
]
