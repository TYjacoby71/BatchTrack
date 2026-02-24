"""Module documentation.

Synopsis:
This module defines route handlers and helpers for `app/blueprints/developer/views/api_routes.py`.

Glossary:
- Route handler: A Flask view function bound to an endpoint.
- Helper unit: A module-level function or class supporting route/service flow.
"""

from __future__ import annotations

from flask import jsonify, request

from app.services.statistics import AnalyticsDataService

from ..decorators import require_developer_permission
from ..routes import developer_bp


# --- Api Stats ---
# Purpose: Define the top-level behavior of `api_stats` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/api/stats")
@require_developer_permission("dev.access_logs")
def api_stats():
    """API endpoint for dashboard statistics."""
    force_refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    overview = AnalyticsDataService.get_system_overview(force_refresh=force_refresh)
    tier_counts = overview.get("tiers") or {}

    stats = {
        "organizations": {
            "total": overview.get("total_organizations", 0),
            "active": overview.get("active_organizations", 0),
            "by_tier": tier_counts,
        },
        "users": {
            "total": overview.get("total_users", 0),
            "active": overview.get("active_users", 0),
        },
    }

    for tier in ["exempt", "free", "solo", "team", "enterprise"]:
        stats["organizations"]["by_tier"].setdefault(tier, 0)

    return jsonify(stats)
