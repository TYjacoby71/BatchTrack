"""
Analytics Data Service

Provides a unified, cached read interface for analytics consumers (developer
inventory analytics UI, global item sidebar, documentation catalog, etc.).
All expensive queries and aggregation logic are centralized here to keep
metrics consistent across surfaces and make future scaling work (materialized
tables, warehouse sync) trivial to swap in.
"""

from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from ...extensions import cache, db
from ...models import (
    GlobalItem,
    InventoryItem,
    Organization,
    Permission,
    Recipe,
    Role,
    UnifiedInventoryHistory,
    User,
)
from ...models.recipe_marketplace import RecipeProductGroup
from ...models.inventory_lot import InventoryLot
from ...models.subscription_tier import SubscriptionTier
from ...models.statistics import RecipeStats
from ...utils.timezone_utils import TimezoneUtils
from ...utils.json_store import read_json_file
from ..dashboard_alerts import DashboardAlertService
from .global_item_stats import GlobalItemStatsService
from ._core import StatisticsService

logger = logging.getLogger(__name__)


class AnalyticsDataService:
    """Single source of truth for application-facing analytics data."""

    _CACHE_PREFIX = "analytics"
    _DEFAULT_TTLS = {
        "metrics": 60,  # seconds
        "top_items": 120,
        "spoilage": 120,
        "data_quality": 300,
        "recent_activity": 30,
        "items_list": 300,
        "global_item_rollup": 300,
        "cost_distribution": 180,
        "organization": 60,
        "system": 60,
        "waitlist": 60,
        "alerts": 30,
        "faults": 60,
        "developer": 60,
        "marketing": 300,
        "recipe_library": 120,
    }

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #

    @classmethod
    def get_inventory_metrics(cls, *, force_refresh: bool = False) -> Dict[str, Optional[float]]:
        """High-level global inventory metrics."""

        cache_key = cls._cache_key("metrics")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            total_items = GlobalItem.query.filter_by(is_archived=False).count()
            linked_adoptions = (
                InventoryItem.query.filter(InventoryItem.global_item_id.isnot(None)).count()
            )

            thirty_days_ago = TimezoneUtils.utc_now() - timedelta(days=30)
            spoilage_events_30d = (
                UnifiedInventoryHistory.query.filter(
                    UnifiedInventoryHistory.change_type.in_(
                        ["spoil", "expired", "damaged", "trash"]
                    ),
                    UnifiedInventoryHistory.timestamp >= thirty_days_ago,
                ).count()
            )

            avg_cost = (
                db.session.query(func.avg(InventoryLot.unit_cost))
                .filter(InventoryLot.unit_cost.isnot(None), InventoryLot.unit_cost > 0)
                .scalar()
            )

            payload = {
                "total_items": total_items,
                "linked_adoptions": linked_adoptions,
                "spoilage_events_30d": spoilage_events_30d,
                "avg_cost_per_unit": float(avg_cost) if avg_cost else None,
            }
            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to compute inventory metrics: %s", exc, exc_info=True)
            return {
                "total_items": 0,
                "linked_adoptions": 0,
                "spoilage_events_30d": 0,
                "avg_cost_per_unit": None,
            }

    @classmethod
    def get_top_global_items(cls, *, limit: int = 10, force_refresh: bool = False) -> List[Dict]:
        """Top global items by adoption count."""

        cache_key = cls._cache_key(f"top_items:{limit}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            rows = (
                db.session.query(
                    GlobalItem.id,
                    GlobalItem.name,
                    func.count(InventoryItem.id).label("org_count"),
                    func.avg(InventoryItem.cost_per_unit).label("avg_cost"),
                )
                .join(InventoryItem, GlobalItem.id == InventoryItem.global_item_id)
                .filter(GlobalItem.is_archived.is_(False))
                .group_by(GlobalItem.id, GlobalItem.name)
                .order_by(func.count(InventoryItem.id).desc())
                .limit(limit)
                .all()
            )

            results = []
            for row in rows:
                results.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "org_count": row.org_count,
                        "avg_cost": float(row.avg_cost) if row.avg_cost else None,
                        "trend": "stable",
                    }
                )
            cls._store_cache(cache_key, results)
            return results
        except SQLAlchemyError as exc:
            logger.error("Failed to compute top global items: %s", exc, exc_info=True)
            return []

    @classmethod
    def get_spoilage_analysis(
        cls, *, days: int = 30, limit: int = 10, force_refresh: bool = False
    ) -> List[Dict]:
        """Spoilage summary grouped by global item across organizations."""

        cache_key = cls._cache_key(f"spoilage:{days}:{limit}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            since = TimezoneUtils.utc_now() - timedelta(days=days)

            rows = (
                db.session.query(
                    GlobalItem.id,
                    GlobalItem.name,
                    func.count(UnifiedInventoryHistory.id).label("event_count"),
                    func.sum(UnifiedInventoryHistory.cost_impact).label("cost_impact"),
                    func.count(func.distinct(UnifiedInventoryHistory.organization_id)).label(
                        "orgs_affected"
                    ),
                )
                .join(InventoryItem, GlobalItem.id == InventoryItem.global_item_id)
                .join(
                    UnifiedInventoryHistory,
                    InventoryItem.id == UnifiedInventoryHistory.inventory_item_id,
                )
                .filter(
                    GlobalItem.is_archived.is_(False),
                    UnifiedInventoryHistory.change_type.in_(
                        ["spoil", "expired", "damaged", "trash"]
                    ),
                    UnifiedInventoryHistory.timestamp >= since,
                )
                .group_by(GlobalItem.id, GlobalItem.name)
                .order_by(func.count(UnifiedInventoryHistory.id).desc())
                .limit(limit)
                .all()
            )

            payload = []
            for row in rows:
                event_count = row.event_count or 0
                # Simple spoilage rate heuristic (0.0 - 1.0 range) mirroring historical stub.
                spoilage_rate = 0.1 if event_count > 5 else round(event_count * 0.02, 4)
                payload.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "spoilage_count": event_count,
                        "spoilage_rate": spoilage_rate,
                        "cost_impact": float(row.cost_impact) if row.cost_impact else 0.0,
                        "orgs_affected": row.orgs_affected or 0,
                    }
                )

            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to compute spoilage analysis: %s", exc, exc_info=True)
            return []

    @classmethod
    def get_data_quality_summary(cls, *, force_refresh: bool = False) -> Dict[str, float]:
        """Data coverage metrics for global item attributes."""

        cache_key = cls._cache_key("data_quality")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            total_items = GlobalItem.query.filter_by(is_archived=False).count()
            if total_items == 0:
                result = {
                    "density_coverage": 0.0,
                    "capacity_coverage": 0.0,
                    "shelf_life_coverage": 0.0,
                }
                cls._store_cache(cache_key, result)
                return result

            def pct(query):
                return round((query.count() / total_items) * 100.0, 2)

            density_coverage = pct(
                GlobalItem.query.filter(
                    GlobalItem.is_archived.is_(False),
                    GlobalItem.density.isnot(None),
                    GlobalItem.density > 0,
                )
            )
            capacity_coverage = pct(
                GlobalItem.query.filter(
                    GlobalItem.is_archived.is_(False),
                    GlobalItem.capacity.isnot(None),
                    GlobalItem.capacity > 0,
                )
            )
            shelf_life_coverage = pct(
                GlobalItem.query.filter(
                    GlobalItem.is_archived.is_(False),
                    GlobalItem.recommended_shelf_life_days.isnot(None),
                    GlobalItem.recommended_shelf_life_days > 0,
                )
            )

            result = {
                "density_coverage": density_coverage,
                "capacity_coverage": capacity_coverage,
                "shelf_life_coverage": shelf_life_coverage,
            }
            cls._store_cache(cache_key, result)
            return result
        except SQLAlchemyError as exc:
            logger.error("Failed to compute data quality summary: %s", exc, exc_info=True)
            return {
                "density_coverage": 0.0,
                "capacity_coverage": 0.0,
                "shelf_life_coverage": 0.0,
            }

    @classmethod
    def get_recent_inventory_activity(
        cls, *, limit: int = 20, force_refresh: bool = False
    ) -> List[Dict]:
        """Recent cross-tenant inventory events."""

        cache_key = cls._cache_key(f"recent_activity:{limit}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            rows = (
                db.session.query(
                    UnifiedInventoryHistory.timestamp,
                    UnifiedInventoryHistory.change_type,
                    UnifiedInventoryHistory.quantity_change,
                    UnifiedInventoryHistory.unit,
                    UnifiedInventoryHistory.cost_impact,
                    Organization.name.label("organization_name"),
                    InventoryItem.name.label("item_name"),
                )
                .join(Organization, UnifiedInventoryHistory.organization_id == Organization.id)
                .join(InventoryItem, UnifiedInventoryHistory.inventory_item_id == InventoryItem.id)
                .order_by(UnifiedInventoryHistory.timestamp.desc())
                .limit(limit)
                .all()
            )

            payload = [
                {
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "organization_name": row.organization_name,
                    "item_name": row.item_name,
                    "action": row.change_type,
                    "quantity_change": float(row.quantity_change)
                    if row.quantity_change is not None
                    else None,
                    "unit": row.unit,
                    "cost_impact": float(row.cost_impact) if row.cost_impact else None,
                }
                for row in rows
            ]
            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to fetch recent inventory activity: %s", exc, exc_info=True)
            return []

    @classmethod
    def get_inventory_item_options(cls, *, force_refresh: bool = False) -> List[Dict]:
        """Distinct global items with at least one organizational adoption."""

        cache_key = cls._cache_key("items_list")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            rows = (
                db.session.query(GlobalItem.id, GlobalItem.name)
                .join(InventoryItem, GlobalItem.id == InventoryItem.global_item_id)
                .filter(GlobalItem.is_archived.is_(False))
                .group_by(GlobalItem.id, GlobalItem.name)
                .having(func.count(InventoryItem.id) > 0)
                .order_by(GlobalItem.name.asc())
                .all()
            )

            payload = [{"id": row.id, "name": row.name} for row in rows]
            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to load inventory item options: %s", exc, exc_info=True)
            return []

    @classmethod
    def get_global_item_rollup(
        cls, global_item_id: int, *, force_refresh: bool = False
    ) -> Dict[str, Optional[float]]:
        """Rollup statistics for a single global item."""

        cache_key = cls._cache_key(f"global_item_rollup:{global_item_id}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        result = GlobalItemStatsService.get_rollup(global_item_id)
        cls._store_cache(cache_key, result)
        return result

    @classmethod
    def get_cost_distribution(
        cls, global_item_id: int, *, force_refresh: bool = False
    ) -> Dict[str, Optional[float]]:
        """Cost distribution for a global item (reuses global stats service)."""

        cache_key = cls._cache_key(f"cost_distribution:{global_item_id}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        result = GlobalItemStatsService.get_cost_distribution(global_item_id)
        cls._store_cache(cache_key, result)
        return result

    @classmethod
    def get_organization_dashboard(
        cls, organization_id: int, *, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Return cached organization dashboard metrics."""

        cache_key = cls._cache_key(f"organization:{organization_id}:overview")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            payload = StatisticsService.get_organization_dashboard_stats(organization_id) or {}
            cls._store_cache(cache_key, payload)
            return payload
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Failed to build organization dashboard for org %s: %s",
                organization_id,
                exc,
                exc_info=True,
            )
            return {}

    @classmethod
    def get_system_overview(cls, *, force_refresh: bool = False) -> Dict[str, int]:
        """Aggregate system-wide counts for developer dashboards."""

        cache_key = cls._cache_key("system:overview")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            total_organizations = Organization.query.count()
            active_organizations = Organization.query.filter_by(is_active=True).count()
            total_users = User.query.filter(User.user_type != 'developer').count()
            active_users = (
                User.query.filter(
                    User.user_type != 'developer',
                    User.is_active.is_(True),
                ).count()
            )
            total_global_items = GlobalItem.query.filter_by(is_archived=False).count()
            total_permissions = Permission.query.count()
            total_roles = Role.query.count()
            recipe_metrics = cls.get_recipe_library_metrics(force_refresh=force_refresh)
            tier_counts = cls._get_subscription_tier_counts()

            payload = {
                "total_organizations": total_organizations,
                "active_organizations": active_organizations,
                "total_users": total_users,
                "active_users": active_users,
                "total_global_items": total_global_items,
                "total_permissions": total_permissions,
                "total_roles": total_roles,
                "tiers": tier_counts,
                "public_recipes": recipe_metrics["total_public"],
                "recipes_for_sale": recipe_metrics["total_for_sale"],
                "blocked_recipes": recipe_metrics["blocked_listings"],
                "average_recipe_price": recipe_metrics["average_sale_price"],
                "average_yield_per_dollar": recipe_metrics["average_yield_per_dollar"],
                "batchtrack_native_recipes": recipe_metrics["batchtrack_native_count"],
                "total_recipe_downloads": recipe_metrics["total_downloads"],
                "total_recipe_purchases": recipe_metrics["total_purchases"],
            }
            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to compute system overview: %s", exc, exc_info=True)
            return {
                "total_organizations": 0,
                "active_organizations": 0,
                "total_users": 0,
                "active_users": 0,
                "total_global_items": 0,
                "total_permissions": 0,
                "total_roles": 0,
                "tiers": {},
                "public_recipes": 0,
                "recipes_for_sale": 0,
                "blocked_recipes": 0,
                "average_recipe_price": 0.0,
                "average_yield_per_dollar": 0.0,
                "batchtrack_native_recipes": 0,
                "total_recipe_downloads": 0,
                "total_recipe_purchases": 0,
            }

    @classmethod
    def get_developer_dashboard(cls, *, force_refresh: bool = False) -> Dict[str, Any]:
        """Aggregate data for the developer dashboard."""

        cache_key = cls._cache_key("developer:dashboard")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            now = TimezoneUtils.utc_now()
            overview = cls.get_system_overview(force_refresh=force_refresh)

            thirty_days_ago = now - timedelta(days=30)
            recent_org_rows = (
                Organization.query.filter(Organization.created_at >= thirty_days_ago)
                .order_by(Organization.created_at.desc())
                .limit(10)
                .all()
            )
            recent_orgs = [
                {
                    "id": org.id,
                    "name": org.name,
                    "subscription_tier": getattr(org.subscription_tier, "name", None),
                    "created_at": org.created_at.isoformat() if org.created_at else None,
                    "created_at_display": org.created_at.strftime("%m/%d")
                    if org.created_at
                    else None,
                }
                for org in recent_org_rows
            ]

            attention_orgs = []
            active_orgs = Organization.query.filter(Organization.is_active.is_(True)).all()
            for org in active_orgs:
                active_users_count = getattr(org, "active_users_count", 0)
                if active_users_count == 0:
                    attention_orgs.append(
                        {
                            "id": org.id,
                            "name": org.name,
                            "subscription_tier": getattr(org.subscription_tier, "name", None),
                            "reason": "no_active_users",
                        }
                    )

            waitlist_entries = read_json_file("data/waitlist.json", default=[]) or []
            waitlist_count = len(waitlist_entries)

            payload = {
                "overview": overview,
                "recent_organizations": recent_orgs,
                "recent_count": len(recent_orgs),
                "attention_organizations": attention_orgs,
                "attention_count": len(attention_orgs),
                "waitlist_count": waitlist_count,
                "generated_at": now.isoformat(),
            }
            cls._store_cache(cache_key, payload)
            return payload
        except Exception as exc:
            logger.error("Failed to build developer dashboard: %s", exc, exc_info=True)
            return {
                "overview": {},
                "recent_organizations": [],
                "recent_count": 0,
                "attention_organizations": [],
                "attention_count": 0,
                "waitlist_count": 0,
                "generated_at": None,
            }
    @classmethod
    def get_recipe_library_metrics(cls, *, force_refresh: bool = False) -> Dict[str, Any]:
        cache_key = cls._cache_key("recipe_library")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        try:
            base_filter = (
                (Recipe.is_public.is_(True)) &
                (Recipe.marketplace_status == "listed") &
                (Recipe.marketplace_blocked.is_(False))
            )
            total_public = Recipe.query.filter(base_filter).count()
            total_for_sale = Recipe.query.filter(base_filter, Recipe.is_for_sale.is_(True)).count()
            blocked_listings = Recipe.query.filter(Recipe.marketplace_blocked.is_(True)).count()
            avg_price = (
                db.session.query(func.avg(Recipe.sale_price))
                .filter(base_filter, Recipe.is_for_sale.is_(True), Recipe.sale_price.isnot(None))
                .scalar()
            ) or 0.0

            top_group_row = (
                db.session.query(RecipeProductGroup.name, func.count(Recipe.id))
                .join(Recipe, Recipe.product_group_id == RecipeProductGroup.id)
                .filter(base_filter)
                .group_by(RecipeProductGroup.name)
                .order_by(func.count(Recipe.id).desc())
                .first()
            )
            top_group_name = top_group_row[0] if top_group_row else None
            top_group_count = top_group_row[1] if top_group_row else None

            batchtrack_native_count = Recipe.query.filter(
                base_filter,
                Recipe.org_origin_type == "batchtrack_native",
            ).count()
            total_downloads = (
                db.session.query(func.sum(Recipe.download_count))
                .filter(base_filter)
                .scalar()
                or 0
            )
            total_purchases = (
                db.session.query(func.sum(Recipe.purchase_count))
                .filter(base_filter)
                .scalar()
                or 0
            )

            avg_yield_per_dollar = (
                db.session.query(
                    func.avg(
                        func.nullif(Recipe.predicted_yield, 0) / func.nullif(RecipeStats.avg_cost_per_batch, 0)
                    )
                )
                .join(RecipeStats, RecipeStats.recipe_id == Recipe.id)
                .filter(
                    base_filter,
                    RecipeStats.avg_cost_per_batch.isnot(None),
                    RecipeStats.avg_cost_per_batch > 0,
                    Recipe.predicted_yield.isnot(None),
                    Recipe.predicted_yield > 0,
                )
                .scalar()
            ) or 0.0

            sale_percentage = 0
            if total_public:
                sale_percentage = round((total_for_sale / total_public) * 100, 1)

            payload = {
                "total_public": total_public,
                "total_for_sale": total_for_sale,
                "blocked_listings": blocked_listings,
                "average_sale_price": float(avg_price),
                "average_yield_per_dollar": float(avg_yield_per_dollar),
                "top_group_name": top_group_name,
                "top_group_count": top_group_count,
                "sale_percentage": sale_percentage,
                "batchtrack_native_count": batchtrack_native_count,
                "total_downloads": int(total_downloads),
                "total_purchases": int(total_purchases),
            }
            cls._store_cache(cache_key, payload)
            return payload
        except SQLAlchemyError as exc:
            logger.error("Failed to compute recipe library metrics: %s", exc, exc_info=True)
            return {
                "total_public": 0,
                "total_for_sale": 0,
                "blocked_listings": 0,
                "average_sale_price": 0.0,
                "average_yield_per_dollar": 0.0,
                "top_group_name": None,
                "top_group_count": 0,
                "sale_percentage": 0,
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to build developer dashboard analytics: %s", exc, exc_info=True)
            return {
                "overview": {},
                "recent_organizations": [],
                "attention_organizations": [],
                "waitlist_count": 0,
                "generated_at": None,
            }

    @classmethod
    def get_waitlist_statistics(cls, *, force_refresh: bool = False) -> Dict[str, Any]:
        """Return processed waitlist entries from all sources for developer views."""

        cache_key = cls._cache_key("waitlist:entries")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        # Define all waitlist sources
        waitlist_sources = {
            'homepage': 'data/waitlist.json',
            'tools_soap': 'data/waitlist_soap.json',
            'tools_candles': 'data/waitlist_candles.json', 
            'tools_lotions': 'data/waitlist_lotions.json',
            'tools_herbal': 'data/waitlist_herbal.json',
            'tools_baker': 'data/waitlist_baker.json',
            'tools_general': 'data/waitlist_tools.json'
        }

        all_entries = []
        source_stats = {}
        
        # Process each waitlist source
        for source_name, file_path in waitlist_sources.items():
            waitlist_data = read_json_file(file_path, default=[]) or []
            source_stats[source_name] = len(waitlist_data)
            
            for entry in waitlist_data:
                timestamp = entry.get("timestamp")
                formatted = "Unknown"
                iso_value = None
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        formatted = dt.strftime("%Y-%m-%d %H:%M UTC")
                        iso_value = dt.isoformat()
                    except Exception:
                        formatted = timestamp
                        iso_value = timestamp

                first_name = entry.get("first_name", "")
                last_name = entry.get("last_name", "")
                legacy_name = entry.get("name", "")
                if first_name or last_name:
                    full_name = f"{first_name} {last_name}".strip()
                elif legacy_name:
                    full_name = legacy_name
                else:
                    full_name = "Not provided"

                all_entries.append(
                    {
                        "email": entry.get("email", ""),
                        "full_name": full_name,
                        "business_type": entry.get("business_type", "Not specified"),
                        "tool_interest": entry.get("tool_interest", ""),
                        "formatted_date": formatted,
                        "timestamp": iso_value,
                        "source": entry.get("source", source_name),
                        "source_display": source_name.replace('_', ' ').title(),
                    }
                )

        # Sort all entries by timestamp
        all_entries.sort(key=lambda item: item.get("timestamp") or "", reverse=True)

        payload = {
            "entries": all_entries,
            "total": len(all_entries),
            "source_breakdown": source_stats,
            "generated_at": TimezoneUtils.utc_now().isoformat(),
        }
        cls._store_cache(cache_key, payload)
        return payload

    @classmethod
    def get_dashboard_alerts(
        cls,
        *,
        dismissed_alerts: Optional[List[str]] = None,
        max_alerts: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return cached dashboard alerts keyed by dismissed list."""

        dismissed_alerts = dismissed_alerts or []
        sorted_key = tuple(sorted(dismissed_alerts))
        limit = max_alerts or 3
        key_suffix = "|".join(sorted_key)
        cache_key = cls._cache_key(f"alerts:{limit}:{key_suffix}")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        alert_data = DashboardAlertService.get_dashboard_alerts(
            max_alerts=limit,
            dismissed_alerts=list(sorted_key),
        )
        cls._store_cache(cache_key, alert_data)
        return alert_data

    @classmethod
    def get_fault_log_entries(
        cls,
        *,
        organization_id: Optional[int] = None,
        include_all: bool = False,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return cached fault log entries (optionally scoped to an organization)."""

        base_key = cls._cache_key("faults:raw")
        raw_entries = cls._get_cached(base_key, force_refresh)
        if raw_entries is None:
            raw_entries = read_json_file("faults.json", default=[]) or []
            raw_entries.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
            cls._store_cache(base_key, raw_entries)

        if include_all or organization_id is None:
            return list(raw_entries)

        scoped_key = cls._cache_key(f"faults:org:{organization_id}")
        scoped_entries = cls._get_cached(scoped_key, force_refresh)
        if scoped_entries is None:
            scoped_entries = [
                fault for fault in raw_entries
                if fault.get("organization_id") == organization_id
            ]
            cls._store_cache(scoped_key, scoped_entries)
        return list(scoped_entries)

    @classmethod
    def get_marketing_content(cls, *, force_refresh: bool = False) -> Dict[str, Any]:
        """Return marketing review/spotlight configuration."""

        cache_key = cls._cache_key("marketing:content")
        cached = cls._get_cached(cache_key, force_refresh)
        if cached is not None:
            return cached

        reviews = read_json_file("data/reviews.json", default=[]) or []
        spotlights = read_json_file("data/spotlights.json", default=[]) or []
        settings = read_json_file("settings.json", default={}) or {}

        payload = {
            "reviews": reviews,
            "spotlights": spotlights,
            "marketing_messages": settings.get("marketing_messages", {}),
            "promo_codes": settings.get("promo_codes", []) or [],
            "demo_url": settings.get("demo_url"),
            "demo_videos": settings.get("demo_videos", []) or [],
        }
        cls._store_cache(cache_key, payload)
        return payload

    @classmethod
    def invalidate_cache(cls):
        """Invalidate all cached analytics payloads."""

        if not cache:
            return
        prefix = cls._CACHE_PREFIX
        try:
            backend = getattr(cache, "cache", None)
            if hasattr(backend, "delete_many"):
                # Try to delete using prefix scan if backend supports it (e.g., Redis).
                keys = []
                if hasattr(backend, "keys"):
                    keys = [key for key in backend.keys(f"{prefix}*")]  # type: ignore[attr-defined]
                elif hasattr(backend, "iter_keys"):
                    keys = [key for key in backend.iter_keys(f"{prefix}*")]  # type: ignore[attr-defined]
                if keys:
                    backend.delete_many(*keys)
            else:
                # Fallback: clear entire cache namespace if available or log warning.
                cache.clear()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed to invalidate analytics cache: %s", exc)

    # Backwards compatibility alias
    invalidate_inventory_cache = invalidate_cache

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def _cache_key(cls, name: str) -> str:
        return f"{cls._CACHE_PREFIX}:{name}"

    @classmethod
    def _get_cached(cls, key: str, force_refresh: bool):
        if force_refresh or not cache:
            return None
        try:
            return cache.get(key)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Cache get failed for %s: %s", key, exc)
            return None

    @classmethod
    def _store_cache(cls, key: str, value, timeout: Optional[int] = None):
        if not cache:
            return
        cache_segment = key.split(":", 2)[-1]
        cache_group = cache_segment.split(":", 1)[0]
        ttl = timeout or cls._DEFAULT_TTLS.get(cache_group, 60)
        try:
            cache.set(key, value, timeout=ttl)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Cache set failed for %s: %s", key, exc)

    @classmethod
    def _get_subscription_tier_counts(cls) -> Dict[str, int]:
        """Return counts of organizations by subscription tier name."""

        try:
            rows = (
                db.session.query(
                    SubscriptionTier.name,
                    func.count(Organization.id).label("org_count"),
                )
                .outerjoin(Organization, Organization.subscription_tier_id == SubscriptionTier.id)
                .group_by(SubscriptionTier.id, SubscriptionTier.name)
                .all()
            )
            # Include explicit names even if zero to preserve known tiers
            counts = {row.name.lower() if row.name else 'unknown': row.org_count for row in rows if row.name}

            # Ensure standard tiers always present
            for key in ["exempt", "free", "solo", "team", "enterprise"]:
                counts.setdefault(key, 0)

            # Count orgs without a mapped tier
            unspecified = (
                Organization.query.filter(Organization.subscription_tier_id.is_(None)).count()
            )
            if unspecified:
                counts["unspecified"] = unspecified
            return counts
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            logger.debug("Failed to compute subscription tier counts: %s", exc)
            return {}


__all__ = ["AnalyticsDataService"]

