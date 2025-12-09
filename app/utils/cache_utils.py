import hashlib
import json
from typing import Any


def _normalize(value: Any) -> Any:
    """Recursively normalize values into JSON-serializable primitives."""
    if isinstance(value, dict):
        return {k: _normalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Fallback for objects (e.g., Decimal, UUID)
    return str(value)


def stable_cache_key(prefix: str, payload: Any | None = None) -> str:
    """
    Produce a deterministic cache key using a prefix and arbitrary payload.

    The payload is normalized and hashed to keep keys compact while ensuring
    collisions are exceedingly unlikely.
    """
    if payload is None:
        return prefix

    normalized = _normalize(payload)
    digest_input = json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    return f"{prefix}:{digest}"
