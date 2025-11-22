
from __future__ import annotations

from typing import Optional, Union

__all__ = ["validate_density", "get_density_description"]

_MIN_DENSITY = 0.01  # g/ml
_MAX_DENSITY = 10.0  # g/ml
_DENSITY_SEGMENTS = (
    (0.5, "very light"),
    (0.9, "light"),
    (1.1, "medium"),
    (1.5, "heavy"),
)


def validate_density(density_value: Union[float, int, str, None]) -> Optional[float]:
    """Return a normalized density (g/ml) when the value falls within sane bounds."""
    if density_value is None:
        return None

    try:
        density = float(density_value)
    except (TypeError, ValueError):
        return None

    return density if _MIN_DENSITY <= density <= _MAX_DENSITY else None


def get_density_description(density: Optional[float]) -> str:
    """Provide a short descriptor for a validated density value."""
    normalized = validate_density(density)
    if normalized is None:
        return "Density not set"

    for threshold, label in _DENSITY_SEGMENTS:
        if normalized < threshold:
            return f"{normalized:.2f} g/ml ({label})"

    return f"{normalized:.2f} g/ml (very heavy)"
