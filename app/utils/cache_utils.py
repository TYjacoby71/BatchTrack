from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from flask import has_request_context, request

__all__ = ["should_bypass_cache", "stable_cache_key"]

_BYPASS_VALUES = {"1", "true", "yes", "force", "refresh"}


def should_bypass_cache() -> bool:
    """
    Determine whether the current request explicitly asked to bypass cached responses.

    Supports:
      - Query param ?refresh=1
      - Header X-Bypass-Cache: 1
      - Cache-Control: no-cache / max-age=0
      - Pragma: no-cache
    """
    if not has_request_context():
        return False

    token = request.args.get("refresh")
    if not token:
        token = request.headers.get("X-Bypass-Cache")
    if token and token.strip().lower() in _BYPASS_VALUES:
        return True

    cache_control = (request.headers.get("Cache-Control") or "").lower()
    if "no-cache" in cache_control or "max-age=0" in cache_control:
        return True

    pragma = (request.headers.get("Pragma") or "").lower()
    if pragma == "no-cache":
        return True

    return False


def stable_cache_key(namespace: str, payload: Mapping[str, Any]) -> str:
    """
    Produce a deterministic hash for the given payload so cache keys remain short.
    """
    try:
        normalized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        )
    except TypeError:
        normalized = json.dumps(str(payload), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    safe_namespace = namespace.strip().replace(" ", "_")
    return f"{safe_namespace}:{digest}"
