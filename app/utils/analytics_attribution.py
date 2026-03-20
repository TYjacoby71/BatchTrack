"""Attribution helpers for click-id analytics propagation.

Synopsis:
Extracts and normalizes ad click identifiers from request surfaces so checkout
and conversion payloads can preserve attribution across redirects.
"""

from __future__ import annotations

from typing import Any

_CLICK_ID_KEYS: tuple[str, ...] = ("gclid", "wbraid", "gbraid")
_COOKIE_PREFIX = "bt_attr_"
_MAX_VALUE_LENGTH = 256


def _normalize_click_id(raw_value: Any) -> str | None:
    if raw_value in (None, ""):
        return None
    parsed = str(raw_value).strip()
    if not parsed:
        return None
    if len(parsed) > _MAX_VALUE_LENGTH:
        parsed = parsed[:_MAX_VALUE_LENGTH]
    return parsed


def extract_click_ids(request) -> dict[str, str]:
    """Return normalized click-id attribution values found on a request."""
    if request is None:
        return {}
    extracted: dict[str, str] = {}
    for key in _CLICK_ID_KEYS:
        candidate = _normalize_click_id(
            request.args.get(key)
            or request.form.get(key)
            or request.cookies.get(_COOKIE_PREFIX + key)
            or request.cookies.get(key)
        )
        if candidate:
            extracted[key] = candidate
    return extracted
