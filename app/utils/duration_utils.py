"""Human-friendly duration formatting helpers.

Synopsis:
Convert raw day counts into readable day/month/year display strings used by
UI and reporting views, with optional inclusion of exact day totals.

Glossary:
- Day count: Integer source value representing elapsed or planned days.
- Humanized duration: Readable label such as ``18 months (540 days)``.
- Positive parse: Integer coercion that rejects non-positive or invalid input.
"""

from __future__ import annotations

from typing import Optional


# --- Humanize day durations ---
# Purpose: Convert day counts into friendly day/month/year labels.
# Inputs: Optional day count and include-days display toggle.
# Outputs: Human-readable duration string or fallback marker.
def humanize_duration_days(days: Optional[int], include_days: bool = True) -> str:
    """Convert a day count to a friendly string (e.g. '18 months (540 days)')."""
    if days is None:
        return "–"

    value = _to_positive_int(days)
    if value is None:
        return "–"

    if value < 60:
        unit = "day" if value == 1 else "days"
        return f"{value} {unit}"

    if value < 730:
        months = value / 30.4375  # average days per month
        months_display = _trim_trailing_zero(round(months, 1))
        unit = "month" if months_display == "1" else "months"
        base = f"{months_display} {unit}"
    else:
        years = value / 365.0
        years_display = _trim_trailing_zero(round(years, 1))
        unit = "year" if years_display == "1" else "years"
        base = f"{years_display} {unit}"

    if include_days:
        base = f"{base} ({value} days)"

    return base


# --- Trim trailing decimal zero ---
# Purpose: Remove redundant .0 from one-decimal float strings.
# Inputs: Rounded float value.
# Outputs: Compact numeric string without unnecessary decimal suffix.
def _trim_trailing_zero(number: float) -> str:
    """Convert a rounded float to string without a trailing .0."""
    text = f"{number:.1f}"
    if text.endswith(".0"):
        return text[:-2]
    return text


# --- Coerce positive integer ---
# Purpose: Normalize optional values into strictly positive integers.
# Inputs: Optional integer-like value.
# Outputs: Positive integer or None when coercion/validation fails.
def _to_positive_int(value: Optional[int]) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
