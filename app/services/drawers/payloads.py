from typing import Dict, Optional


def build_drawer_payload(
    modal_url: str,
    *,
    error_type: str,
    error_code: str,
    success_event: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Dict:
    """Standardized drawer payload builder to keep a consistent contract."""
    if not modal_url or not error_type or not error_code:
        raise ValueError("modal_url, error_type, and error_code are required")

    payload: Dict = {
        "modal_url": modal_url,
        "error_type": error_type,
        "error_code": error_code,
    }
    if success_event:
        payload["success_event"] = success_event
    if correlation_id:
        payload["correlation_id"] = correlation_id
    return payload
