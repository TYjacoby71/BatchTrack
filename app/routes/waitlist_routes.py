
from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.utils.json_store import read_json_file, write_json_file
from app.services.public_bot_trap_service import PublicBotTrapService

waitlist_bp = Blueprint('waitlist', __name__)

_DEFAULT_WAITLIST_KEY = "public_homepage"


def _normalize_waitlist_key(raw_value: Optional[str]) -> str:
    """Return a sanitized waitlist key that is filesystem and analytics safe."""
    if not raw_value or not isinstance(raw_value, str):
        return _DEFAULT_WAITLIST_KEY

    cleaned = raw_value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    return cleaned or _DEFAULT_WAITLIST_KEY


def _extract_waitlist_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize waitlist metadata fields from the request payload."""
    waitlist_key = _normalize_waitlist_key(
        data.get("waitlist_key") or data.get("source") or data.get("list_id")
    )
    source = data.get("source") or waitlist_key
    context = data.get("context") or data.get("origin") or "public_site"

    return {
        "waitlist_key": waitlist_key,
        "source": source,
        "context": context,
    }


@waitlist_bp.route("/api/waitlist", methods=["POST"])
def join_waitlist():
    """Handle waitlist form submissions - save to JSON only."""
    try:
        payload = request.get_json() or {}
        if not isinstance(payload, dict):
            payload = {}

        metadata = _extract_waitlist_metadata(payload)
        trap_value = (payload.get("website") or payload.get("company") or "").strip()
        trap_email = (payload.get("email") or "").strip().lower() or None
        if trap_value:
            PublicBotTrapService.record_hit(
                request=request,
                source=metadata.get("source", "waitlist"),
                reason="waitlist_honeypot",
                email=trap_email,
                extra={"field": "website"},
                block=False,
            )
            if trap_email:
                blocked_user_id = PublicBotTrapService.block_email_if_user_exists(trap_email)
                PublicBotTrapService.add_block(email=trap_email, user_id=blocked_user_id)
            else:
                PublicBotTrapService.add_block(
                    ip=PublicBotTrapService.resolve_request_ip(request),
                )
            return jsonify({"message": "Successfully joined waitlist"}), 200

        email = (payload.get("email") or "").strip()
        if not email:
            return jsonify({"error": "Email is required"}), 400
        email = email.lower()

        first_name = (payload.get("first_name") or "").strip()
        last_name = (payload.get("last_name") or "").strip()
        business_type = (payload.get("business_type") or "").strip()

        if PublicBotTrapService.is_blocked(
            ip=PublicBotTrapService.resolve_request_ip(request),
            email=email,
        ):
            PublicBotTrapService.record_hit(
                request=request,
                source=metadata.get("source", "waitlist"),
                reason="waitlist_blocked",
                email=email,
                extra={"waitlist_key": metadata.get("waitlist_key")},
                block=False,
            )
            return jsonify({"message": "Successfully joined waitlist"}), 200

        waitlist_entry = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "business_type": business_type or "not_specified",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": metadata["source"],
            "waitlist_key": metadata["waitlist_key"],
            "context": metadata["context"],
            "notes": (payload.get("notes") or "").strip(),
            "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
        }

        waitlist_file = "data/waitlist.json"
        waitlist = read_json_file(waitlist_file, default=[]) or []

        if any(entry.get("email") == waitlist_entry["email"] and entry.get("waitlist_key") == waitlist_entry["waitlist_key"] for entry in waitlist):
            return jsonify({"message": "Email already on this waitlist"}), 200

        waitlist.append(waitlist_entry)
        write_json_file(waitlist_file, waitlist)

        return jsonify({"message": "Successfully joined waitlist"}), 200

    except Exception as exc:  # pragma: no cover - defensive
        import traceback

        print("Waitlist error:", exc)
        print("Traceback:", traceback.format_exc())
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "details": str(exc),
                }
            ),
            500,
        )
