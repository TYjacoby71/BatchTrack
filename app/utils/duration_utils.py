from __future__ import annotations

from typing import Optional


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


def _trim_trailing_zero(number: float) -> str:
    """Convert a rounded float to string without a trailing .0."""
    text = f"{number:.1f}"
    if text.endswith(".0"):
        return text[:-2]
    return text


def _to_positive_int(value: Optional[int]) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
