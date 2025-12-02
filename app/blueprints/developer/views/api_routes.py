from __future__ import annotations

from flask import jsonify, request
from flask_login import login_required

from app.services.statistics import AnalyticsDataService

from ..routes import developer_bp


@developer_bp.route("/api/stats")
@login_required
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

    from app.models.subscription_tier import SubscriptionTier

    for tier in ["exempt", "free", "solo", "team", "enterprise"]:
        stats["organizations"]["by_tier"].setdefault(tier, 0)

    return jsonify(stats)
