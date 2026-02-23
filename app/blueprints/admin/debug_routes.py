"""Admin debug routes for FIFO consistency checks.

Synopsis:
Expose authenticated diagnostic endpoints that validate inventory/FIFO parity
across an organization or for a specific inventory item.

Glossary:
- FIFO sync: Consistency between inventory on-hand totals and FIFO lot sums.
- Sync issue: Per-item mismatch payload returned for troubleshooting.
- Debug blueprint: Route namespace containing internal diagnostic handlers.
"""

import logging

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.models import InventoryItem
from app.services.inventory_adjustment._validation import validate_inventory_fifo_sync

# --- Debug blueprint ---
# Purpose: Group internal FIFO validation diagnostics.
# Inputs: None.
# Outputs: Flask blueprint registered under /debug.
debug_bp = Blueprint("debug", __name__, url_prefix="/debug")
logger = logging.getLogger(__name__)


# --- Validate FIFO sync for all items ---
# Purpose: Scan all organization inventory items for FIFO sync mismatches.
# Inputs: Authenticated user context for organization scoping.
# Outputs: JSON summary with counts and per-item mismatch details.
@debug_bp.route("/validate-fifo-sync")
@login_required
def validate_all_fifo_sync():
    """Validate FIFO sync for all inventory items in the organization"""

    # Get all inventory items for the current organization
    items = InventoryItem.query.filter_by(
        organization_id=current_user.organization_id
    ).all()

    sync_issues = []
    valid_count = 0

    for item in items:
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item.id)

        if not is_valid:
            sync_issues.append(
                {
                    "item_id": item.id,
                    "item_name": item.name,
                    "inventory_qty": inv_qty,
                    "fifo_total": fifo_total,
                    "difference": abs(inv_qty - fifo_total),
                    "error_msg": error_msg,
                }
            )
        else:
            valid_count += 1

    result = {
        "total_items": len(items),
        "valid_items": valid_count,
        "sync_issues_count": len(sync_issues),
        "sync_issues": sync_issues,
    }

    if sync_issues:
        logger.warning(
            f"FIFO sync issues found for {len(sync_issues)} items in org {current_user.organization_id}"
        )

    return jsonify(result)


# --- Validate FIFO sync for one item ---
# Purpose: Run FIFO consistency check for a single scoped inventory item.
# Inputs: Inventory item id path parameter.
# Outputs: JSON payload describing validity and mismatch details.
@debug_bp.route("/validate-fifo-sync/<int:item_id>")
@login_required
def validate_single_fifo_sync(item_id):
    """Validate FIFO sync for a specific inventory item"""

    # Verify the item belongs to the current organization
    item = InventoryItem.query.filter_by(
        id=item_id, organization_id=current_user.organization_id
    ).first()

    if not item:
        return jsonify({"error": "Item not found"}), 404

    is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id)

    result = {
        "item_id": item_id,
        "item_name": item.name,
        "is_valid": is_valid,
        "inventory_qty": inv_qty,
        "fifo_total": fifo_total,
        "difference": abs(inv_qty - fifo_total) if inv_qty and fifo_total else 0,
        "error_msg": error_msg,
    }

    return jsonify(result)
