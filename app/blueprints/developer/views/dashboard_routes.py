"""Module documentation.

Synopsis:
This module defines route handlers and helpers for `app/blueprints/developer/views/dashboard_routes.py`.

Glossary:
- Route handler: A Flask view function bound to an endpoint.
- Helper unit: A module-level function or class supporting route/service flow.
"""

from __future__ import annotations
import logging

from flask import jsonify, render_template, request, url_for

from app.models.feature_flag import FeatureFlag
from app.services.developer.dashboard_service import DeveloperDashboardService
from app.services.statistics import AnalyticsDataService

from ..decorators import require_developer_permission
from ..routes import developer_bp

logger = logging.getLogger(__name__)



# --- Dashboard ---
# Purpose: Define the top-level behavior of `dashboard` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/dashboard")
@require_developer_permission("dev.dashboard")
def dashboard():
    """Main developer dashboard overview."""
    force_refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    context = DeveloperDashboardService.build_dashboard_context(
        force_refresh=force_refresh
    )
    context.update(
        {
            "force_refresh": force_refresh,
            "breadcrumb_items": [{"label": "Developer Dashboard"}],
        }
    )
    return render_template("developer/dashboard.html", **context)


# --- Marketing Admin ---
# Purpose: Define the top-level behavior of `marketing_admin` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/marketing-admin")
@require_developer_permission("dev.system_admin")
def marketing_admin():
    """Manage homepage marketing content (reviews, spotlights, messages)."""
    context = DeveloperDashboardService.get_marketing_admin_context()
    return render_template("developer/marketing_admin.html", **context)


# --- Marketing Admin Save ---
# Purpose: Define the top-level behavior of `marketing_admin_save` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/marketing-admin/save", methods=["POST"])
@require_developer_permission("dev.system_admin")
def marketing_admin_save():
    """Persist marketing content to JSON stores."""
    try:
        data = request.get_json() or {}
        DeveloperDashboardService.save_marketing_payload(data)
        return jsonify({"success": True})
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Suppressed exception fallback at app/blueprints/developer/views/dashboard_routes.py:68", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


# --- Batchley Overview ---
# Purpose: Define the top-level behavior of `batchley_overview` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/batchley")
@require_developer_permission("dev.dashboard")
def batchley_overview():
    """Developer view of Batchley's capabilities, limits, and configuration."""
    batchley_context = DeveloperDashboardService.build_batchley_context()
    return render_template(
        "developer/batchley.html",
        job_catalog=batchley_context.job_catalog,
        env_status=batchley_context.env_status,
        limit_cards=batchley_context.limit_cards,
        workflow_notes=batchley_context.workflow_notes,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Batchley"},
        ],
    )


# --- System Settings ---
# Purpose: Define the top-level behavior of `system_settings` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/system-settings")
@require_developer_permission("dev.system_settings")
def system_settings():
    """Developer-only system settings page."""
    from app.utils.json_store import read_json_file

    system_settings = read_json_file("settings.json", default={}) or {}
    defaults = {
        "system": {
            "per_page": 25,
            "enable_csv_export": True,
            "auto_save_forms": False,
            "auto_backup": False,
        },
        "notifications": {
            "browser_notifications": True,
            "email_alerts": False,
            "alert_frequency": "real_time",
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    }

    for section, section_settings in defaults.items():
        if section not in system_settings:
            system_settings[section] = section_settings
        else:
            for key, value in section_settings.items():
                if key not in system_settings[section]:
                    system_settings[section][key] = value

    return render_template(
        "developer/system_settings.html",
        system_settings=system_settings,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "System Settings"},
        ],
    )


# --- Update System Settings ---
# Purpose: Define the top-level behavior of `update_system_settings` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/system-settings/update", methods=["POST"])
@require_developer_permission("dev.system_settings")
def update_system_settings():
    """Persist developer system settings updates."""
    from app.utils.json_store import read_json_file, write_json_file

    data = request.get_json() or {}
    section = data.get("section")
    key = data.get("key")
    value = data.get("value")

    if not section or not key:
        return (
            jsonify({"success": False, "error": "Section and key are required."}),
            400,
        )

    settings_data = read_json_file("settings.json", default={}) or {}
    section_settings = settings_data.get(section)
    if not isinstance(section_settings, dict):
        section_settings = {}
        settings_data[section] = section_settings

    section_settings[key] = value
    write_json_file("settings.json", settings_data)
    return jsonify({"success": True})


# --- Feature Flags ---
# Purpose: Define the top-level behavior of `feature_flags` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/feature-flags")
@require_developer_permission("dev.system_admin")
def feature_flags():
    """Feature flags management page."""
    db_flags = FeatureFlag.query.all()
    flag_state = {flag.key: flag.enabled for flag in db_flags}
    feature_flag_sections = DeveloperDashboardService.get_feature_flag_sections()

    return render_template(
        "developer/feature_flags.html",
        feature_flag_sections=feature_flag_sections,
        flag_state=flag_state,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Feature Flags"},
        ],
    )


# --- System Statistics ---
# Purpose: Define the top-level behavior of `system_statistics` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/system-statistics")
@require_developer_permission("dev.access_logs")
def system_statistics():
    """System-wide statistics dashboard."""
    force_refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    stats = AnalyticsDataService.get_system_overview(force_refresh=force_refresh)
    return render_template("developer/system_statistics.html", stats=stats)


# --- Billing Integration ---
# Purpose: Define the top-level behavior of `billing_integration` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/billing-integration")
@require_developer_permission("dev.view_all_billing")
def billing_integration():
    """Billing integration management shell page."""
    return render_template("developer/billing_integration.html")


# --- Waitlist Statistics ---
# Purpose: Define the top-level behavior of `waitlist_statistics` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/waitlist-statistics")
@require_developer_permission("dev.system_admin")
def waitlist_statistics():
    """View waitlist statistics and data."""
    force_refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    stats = DeveloperDashboardService.get_waitlist_statistics(
        force_refresh=force_refresh
    )
    return render_template(
        "developer/waitlist_statistics.html",
        waitlist_data=stats.get("entries", []),
        total_signups=stats.get("total", 0),
        waitlist_channels=stats.get("channel_summary", []),
        unique_waitlists=stats.get("unique_waitlists", 0),
        generated_at=stats.get("generated_at"),
    )
