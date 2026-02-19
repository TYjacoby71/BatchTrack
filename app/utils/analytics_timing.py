"""Analytics timing helpers.

Synopsis:
Provide shared utilities for computing coarse funnel timing from client hints.

Glossary:
- First landing timestamp: Epoch milliseconds stored client-side at first public visit.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .timezone_utils import TimezoneUtils

_FIRST_LANDING_COOKIE = "bt_first_landing_at"
_MIN_EPOCH_MS = 946684800000  # 2000-01-01 UTC
_MAX_EPOCH_MS = 4102444800000  # 2100-01-01 UTC


# --- Parse first-landing epoch ---
# Purpose: Safely parse the first-landing epoch milliseconds from request cookies.
# Inputs: Flask request object.
# Outputs: Integer epoch milliseconds when valid, otherwise None.
def get_first_landing_epoch_ms(request) -> int | None:
    if request is None:
        return None
    raw_value = request.cookies.get(_FIRST_LANDING_COOKIE)
    if raw_value in (None, ""):
        return None
    try:
        parsed = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None
    if parsed < _MIN_EPOCH_MS or parsed > _MAX_EPOCH_MS:
        return None
    return parsed


# --- Compute seconds since first landing ---
# Purpose: Return elapsed whole seconds from first landing cookie to now.
# Inputs: Flask request object and optional current datetime for testability.
# Outputs: Non-negative elapsed seconds or None when no usable landing timestamp exists.
def seconds_since_first_landing(request, *, now_utc: datetime | None = None) -> int | None:
    first_landing_ms = get_first_landing_epoch_ms(request)
    if first_landing_ms is None:
        return None
    current_time = TimezoneUtils.ensure_timezone_aware(now_utc) if now_utc else None
    if current_time is None:
        current_time = TimezoneUtils.utc_now()
    try:
        first_landing_dt = datetime.fromtimestamp(
            first_landing_ms / 1000.0, tz=timezone.utc
        )
    except (OverflowError, OSError, ValueError):
        return None
    elapsed = (current_time - first_landing_dt).total_seconds()
    if elapsed < 0:
        return 0
    return int(elapsed)

