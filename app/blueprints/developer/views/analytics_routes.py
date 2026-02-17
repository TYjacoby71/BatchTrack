from __future__ import annotations

from flask import flash, jsonify, render_template, request, url_for

from app.services.statistics import (
    AnalyticsCatalogError,
    AnalyticsCatalogService,
    AnalyticsDataService,
)

from ..decorators import require_developer_permission
from ..routes import developer_bp


@developer_bp.route("/inventory-analytics")
@require_developer_permission("dev.access_logs")
def inventory_analytics_stub():
    """Developer inventory analytics."""
    return render_template(
        "developer/inventory_analytics.html",
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Inventory Analytics"},
        ],
    )


@developer_bp.route("/api/inventory-analytics/metrics")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_metrics():
    """Get key inventory analytics metrics."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        return jsonify(
            AnalyticsDataService.get_inventory_metrics(force_refresh=force_refresh)
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/top-items")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_top_items():
    """Get top items by usage across organizations."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        items = AnalyticsDataService.get_top_global_items(force_refresh=force_refresh)
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/spoilage")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_spoilage():
    """Get spoilage analysis by item."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        items = AnalyticsDataService.get_spoilage_analysis(force_refresh=force_refresh)
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/data-quality")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_data_quality():
    """Get data quality metrics for global items."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        return jsonify(
            AnalyticsDataService.get_data_quality_summary(force_refresh=force_refresh)
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/recent-activity")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_recent_activity():
    """Get recent inventory activity across all organizations."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        activities = AnalyticsDataService.get_recent_inventory_activity(
            force_refresh=force_refresh
        )
        return jsonify({"activities": activities})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/items-list")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_items_list():
    """Get list of global items for selection."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        items = AnalyticsDataService.get_inventory_item_options(
            force_refresh=force_refresh
        )
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/api/inventory-analytics/cost-distribution/<int:item_id>")
@require_developer_permission("dev.access_logs")
def api_inventory_analytics_cost_distribution(item_id):
    """Get cost distribution for a specific global item."""
    try:
        force_refresh = (request.args.get("refresh") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        distribution = AnalyticsDataService.get_cost_distribution(
            item_id, force_refresh=force_refresh
        )
        return jsonify(distribution)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@developer_bp.route("/analytics-catalog")
@require_developer_permission("dev.access_logs")
def analytics_catalog():
    """Developer catalog of analytics data points and domains."""
    from flask import current_app

    try:
        domains = AnalyticsCatalogService.get_domains()
        summary = AnalyticsCatalogService.get_summary()
    except AnalyticsCatalogError as exc:
        current_app.logger.error(
            "Failed to build analytics catalog: %s", exc, exc_info=True
        )
        flash(
            "Unable to load the analytics catalog right now. Please try again later.",
            "error",
        )
        domains = []
        summary = None

    return render_template(
        "developer/analytics_catalog.html",
        domains=domains,
        catalog_summary=summary,
    )
