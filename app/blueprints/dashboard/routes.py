"""Dashboard and shared app route handlers.

Synopsis:
Provide documented top-level behavior for `app/blueprints/dashboard/routes.py` without altering runtime logic.

Glossary:
- Module path: Source file `app/blueprints/dashboard/routes.py`.
- Unit heading block: Standardized comment metadata above each top-level function/class.
"""

import logging

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.blueprints.expiration.services import ExpirationService
from app.extensions import limiter
from app.services.app_dashboard_service import AppDashboardService
from app.services.combined_inventory_alerts import CombinedInventoryAlertService
from app.services.statistics import AnalyticsDataService
from app.utils.permissions import get_effective_organization_id, permission_required

logger = logging.getLogger(__name__)

app_routes_bp = Blueprint("app_routes", __name__)

# Dashboard no longer performs stock checks - this is handled by production planning


def _effective_org_id() -> int | None:
    """Resolve effective organization scope for dashboard routes."""
    return get_effective_organization_id()


# --- Dashboard ---
# Purpose: Implement `dashboard` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@app_routes_bp.route("/dashboard")
@app_routes_bp.route("/user_dashboard")
@login_required
@limiter.limit("1000 per minute")
@permission_required("dashboard.view")
def dashboard():
    """Main dashboard view with stock checking and alerts."""
    effective_org_id = _effective_org_id()
    if not effective_org_id:
        flash("Select an organization to view this dashboard.", "warning")
        return redirect(url_for("settings.index"))

    try:
        selected_org_exists = AppDashboardService.organization_exists(effective_org_id)
    except Exception as org_error:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/dashboard/routes.py:74",
            exc_info=True,
        )
        print("---!!! ORGANIZATION QUERY ERROR (ORIGINAL SIN?) !!!---")
        print(f"Error: {org_error}")
        print("----------------------------------------------------")
        AppDashboardService.rollback_session()
        flash("Database error accessing organization. Please try again.", "error")
        return redirect(url_for("settings.index"))
    if not selected_org_exists:
        session.pop("dev_selected_org_id", None)
        session.pop("dev_masquerade_context", None)
        flash(
            "Selected organization no longer exists. Masquerade cleared.",
            "error",
        )
        return redirect(url_for("settings.index"))

    # Initialize with safe defaults.
    active_batch = None
    low_stock_ingredients = []
    expiration_summary = {
        "expired_fifo": 0,
        "expiring_fifo": 0,
        "expired_products": 0,
        "expiring_products": 0,
    }

    try:
        # Force clean state.
        AppDashboardService.rollback_session()

        # Get active batch with explicit error catching.
        try:
            active_batch = AppDashboardService.get_active_in_progress_batch(
                organization_id=effective_org_id
            )
        except Exception as batch_error:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/dashboard/routes.py:105",
                exc_info=True,
            )
            print("---!!! BATCH QUERY ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {batch_error}")
            print("-----------------------------------------------")
            AppDashboardService.rollback_session()
            active_batch = None

        # Get inventory alerts with explicit error catching.
        try:
            low_stock_ingredients = (
                CombinedInventoryAlertService.get_low_stock_ingredients()
            )
        except Exception as inv_error:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/dashboard/routes.py:132",
                exc_info=True,
            )
            print("---!!! INVENTORY ALERTS ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {inv_error}")
            print("----------------------------------------------------")
            AppDashboardService.rollback_session()
            low_stock_ingredients = []

        # Get expiration summary with explicit error catching.
        try:
            expiration_summary = ExpirationService.get_expiration_summary()
        except Exception as exp_error:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/dashboard/routes.py:142",
                exc_info=True,
            )
            print("---!!! EXPIRATION SERVICE ERROR (ORIGINAL SIN?) !!!---")
            print(f"Error: {exp_error}")
            print("------------------------------------------------------")
            AppDashboardService.rollback_session()
            expiration_summary = {
                "expired_fifo": 0,
                "expiring_fifo": 0,
                "expired_products": 0,
                "expiring_products": 0,
            }

    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/dashboard/routes.py:154",
            exc_info=True,
        )
        print("---!!! GENERAL DASHBOARD ERROR !!!---")
        print(f"Error: {exc}")
        print("------------------------------------")
        AppDashboardService.rollback_session()
        flash(
            "Dashboard temporarily unavailable. Please try refreshing the page.",
            "error",
        )

    return render_template(
        "dashboard.html",
        active_batch=active_batch,
        current_user=current_user,
        low_stock_ingredients=low_stock_ingredients,
        expiration_summary=expiration_summary,
    )


# --- Unit Manager ---
# Purpose: Implement `unit_manager` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@app_routes_bp.route("/unit-manager")
@login_required
@permission_required("inventory.edit")
def unit_manager():
    return redirect(url_for("conversion.manage_units"))


# --- Auth Check ---
# Purpose: Implement `auth_check` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@app_routes_bp.route("/auth-check", methods=["GET"])
@login_required
@limiter.limit("500 per minute")
@permission_required("dashboard.view")
def auth_check():
    """Lightweight endpoint to verify authentication status without heavy DB work."""
    return jsonify({"status": "ok"})


# --- View Fault Log ---
# Purpose: Implement `view_fault_log` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@app_routes_bp.route("/fault-log")
@login_required
@permission_required("alerts.view")
def view_fault_log():
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        effective_org_id = _effective_org_id()
        if effective_org_id:
            faults = AnalyticsDataService.get_fault_log_entries(
                organization_id=effective_org_id,
                include_all=False,
                force_refresh=force_refresh,
            )
        else:
            faults = []

        return render_template("fault_log.html", faults=faults)
    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/dashboard/routes.py:290",
            exc_info=True,
        )
        flash(f"Error loading fault log: {str(exc)}", "error")
        return render_template("fault_log.html", faults=[])


# --- Vendor Signup ---
# Purpose: Implement `vendor_signup` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@app_routes_bp.route("/api/vendor-signup", methods=["POST"])
@limiter.limit("10 per minute")
def vendor_signup():
    """Handle vendor signup submissions."""
    try:
        import os
        import re

        from app.utils.json_store import read_json_file, write_json_file
        from app.utils.timezone_utils import TimezoneUtils

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Validate required fields.
        required_fields = [
            "item_name",
            "item_id",
            "company_name",
            "contact_name",
            "email",
        ]
        for field in required_fields:
            if not data.get(field):
                return (
                    jsonify(
                        {"success": False, "error": f"Missing required field: {field}"}
                    ),
                    400,
                )

        # Validate email format.
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, data["email"]):
            return jsonify({"success": False, "error": "Invalid email format"}), 400

        # Ensure data directory exists.
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)

        # Read existing vendor signups.
        vendor_file = os.path.join(data_dir, "vendor_signups.json")
        vendor_signups = read_json_file(vendor_file, default=[])

        # Add new signup.
        signup_data = {
            "id": len(vendor_signups) + 1,
            "item_name": data["item_name"],
            "item_id": data["item_id"],
            "company_name": data["company_name"],
            "contact_name": data["contact_name"],
            "email": data["email"],
            "phone": data.get("phone", ""),
            "website": data.get("website", ""),
            "message": data.get("message", ""),
            "timestamp": TimezoneUtils.utc_now().isoformat(),
            "status": "pending",
        }

        vendor_signups.append(signup_data)

        # Save updated list.
        write_json_file(vendor_file, vendor_signups)

        return jsonify(
            {"success": True, "message": "Vendor signup submitted successfully"}
        )

    except Exception as exc:
        logger.error(f"Vendor signup error: {exc}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


