from __future__ import annotations

from typing import Any, Dict, Optional

def build_drawer_payload(
    *,
    error_type: str,
    error_code: str,
    modal_url: Optional[str] = None,
    redirect_url: Optional[str] = None,
    success_event: Optional[str] = None,
    correlation_id: Optional[str] = None,
    error_message: Optional[str] = None,
    retry: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """Standardized drawer payload builder to keep a consistent contract."""
    if not error_type or not error_code:
        raise ValueError("error_type and error_code are required")
    if bool(modal_url) == bool(redirect_url):
        raise ValueError("Exactly one of modal_url or redirect_url is required")

    payload: Dict = {
        "version": "1.0",
        "protocol": "drawer.v1",
        "modal_url": modal_url,
        "redirect_url": redirect_url,
        "error_type": error_type,
        "error_code": error_code,
    }
    if success_event:
        payload["success_event"] = success_event
    if correlation_id:
        payload["correlation_id"] = correlation_id
    if error_message:
        payload["error_message"] = error_message
    if retry:
        payload["retry"] = {
            "operation": retry.get("operation"),
            "data": retry.get("data", {}),
        }
    if metadata:
        payload["metadata"] = metadata

    # Remove empty destination field for cleaner payloads.
    if payload.get("modal_url") is None:
        payload.pop("modal_url", None)
    if payload.get("redirect_url") is None:
        payload.pop("redirect_url", None)

    return payload
