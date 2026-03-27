"""Global link drawer actions.

Synopsis:
Surface global-item linking suggestions and render the link modal.

Glossary:
- Global item: Canonical catalog entry for ingredients.
- Suggestion drawer: UI prompt to link local items to global items.
"""

import logging

from flask import jsonify, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.drawers.payloads import build_drawer_payload
from app.services.global_link_drawer_service import GlobalLinkDrawerService
from app.services.global_link_suggestions import GlobalLinkSuggestionService
from app.utils.permissions import require_permission

from .. import drawers_bp, register_cadence_check, register_drawer_action

logger = logging.getLogger(__name__)


register_drawer_action(
    "global_link.modal",
    description="Link local inventory items to curated Global Items.",
    endpoint="drawers.global_link_modal",
    success_event="globalLinking.completed",
)


# ---  Build Global Link Payload ---
# Purpose: Implement `_build_global_link_payload` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _build_global_link_payload(global_item_id: int | None):
    if not global_item_id:
        return None
    return build_drawer_payload(
        modal_url=url_for("drawers.global_link_modal", global_item_id=global_item_id),
        error_type="global_link",
        error_code="SUGGESTIONS_FOUND",
        success_event="globalLinking.completed",
    )


# ---  Global Link Drawer Payload ---
# Purpose: Implement `_global_link_drawer_payload` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _global_link_drawer_payload():
    org_id = getattr(current_user, "organization_id", None)
    if not org_id:
        return None

    global_item, items = GlobalLinkSuggestionService.get_first_suggestion_for_org(
        org_id
    )
    if not (global_item and items):
        return None

    payload = _build_global_link_payload(global_item.id)
    payload["metadata"] = {"suggested_count": len(items)}
    return payload


# =========================================================
# GLOBAL LINK DRAWER
# =========================================================
# --- Cadence check ---
# Purpose: Provide drawer payload for cadence checks.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@register_cadence_check("global_link")
def global_link_cadence_check():
    if not current_user.is_authenticated:
        return None
    return _global_link_drawer_payload()


# --- Drawer check ---
# Purpose: Report whether the global link drawer should display.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@drawers_bp.route("/global-link/check", methods=["GET"])
@login_required
@require_permission("inventory.view")
def global_link_check():
    """Check whether the org has suggested global link matches."""
    payload = _global_link_drawer_payload()
    return jsonify({"needs_drawer": payload is not None, "drawer_payload": payload})


# --- Drawer modal ---
# Purpose: Render the global link modal for suggested items.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@drawers_bp.route("/global-link/modal", methods=["GET"])
@login_required
@require_permission("inventory.view")
def global_link_modal():
    global_item_id = request.args.get("global_item_id", type=int)
    org_id = getattr(current_user, "organization_id", None)
    global_item, items = GlobalLinkDrawerService.get_modal_candidates(
        global_item_id=global_item_id,
        organization_id=org_id,
    )

    if not global_item or not org_id:
        return jsonify({"success": False, "error": "Invalid request"}), 400

    html = render_template(
        "components/drawer/global_link_modal.html", global_item=global_item, items=items
    )
    return jsonify({"success": True, "modal_html": html})


# --- Drawer confirm ---
# Purpose: Link selected inventory items to a global item.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@drawers_bp.route("/global-link/confirm", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def global_link_confirm():
    data = request.get_json(force=True) or {}
    global_item_id = data.get("global_item_id")
    item_ids = data.get("item_ids") or []

    global_item = (
        GlobalLinkDrawerService.get_global_item(int(global_item_id))
        if global_item_id
        else None
    )
    if not global_item:
        return jsonify({"success": False, "error": "Global item not found"}), 404

    try:
        updated, skipped = GlobalLinkDrawerService.link_items_to_global(
            global_item=global_item,
            item_ids=item_ids,
            actor_org_id=getattr(current_user, "organization_id", None),
            actor_user_id=getattr(current_user, "id", None),
        )
    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/drawers/drawer_actions/global_link.py:189",
            exc_info=True,
        )
        return jsonify({"success": False, "error": str(exc)}), 500

    return jsonify({"success": True, "updated": updated, "skipped": skipped})
