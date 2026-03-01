"""Central analytics catalog definitions.

Provides a single source of truth for the analytics domains we expose to
developers and for downstream warehouse pipelines.  The goal is to make it
obvious which tables, aggregates, and dimensions power each analytics surface.
"""

from __future__ import annotations
import logging

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class CatalogDomain:
    """Structured description for a single analytics domain."""

    key: str
    name: str
    description: str
    storage: List[Dict[str, Any]]
    metrics: List[str]
    dimensions: List[str]
    events: List[str]
    feeds: List[str]
    consumers: List[str]


class AnalyticsCatalogError(RuntimeError):
    """Raised when the analytics catalog cannot be produced."""


class AnalyticsCatalogService:
    """Expose analytics catalog metadata for UI and documentation."""

    _CATALOG_VERSION = "2025.11"
    _UPDATED_AT = datetime(2025, 11, 6, tzinfo=timezone.utc)

    # NOTE: Keep this list ordered by core production domain → supporting domains.
    _DOMAINS: List[CatalogDomain] = [
        CatalogDomain(
            key="inventory",
            name="Inventory & Lots",
            description=(
                "Per-organization inventory master data, lot costs, freshness and "
                "quantity movement history. Provides the canonical source for "
                "per-item centralized stats and cost benchmarking."
            ),
            storage=[
                {
                    "model": "InventoryItem",
                    "table": "inventory_item",
                    "scope": "organization",
                    "notes": "One row per org item; links to global item, density metadata, ownership semantics.",
                },
                {
                    "model": "InventoryLot",
                    "table": "inventory_lot",
                    "scope": "organization",
                    "notes": "FIFO lots with received/expiration timestamps and unit cost for cost curves.",
                },
                {
                    "model": "UnifiedInventoryHistory",
                    "table": "unified_inventory_history",
                    "scope": "event_log",
                    "notes": "Normalized movement log with change_type, location_id and batch references.",
                },
                {
                    "model": "FreshnessSnapshot",
                    "table": "freshness_snapshot",
                    "scope": "daily_snapshot",
                    "notes": "Per-item freshness efficiency scores generated daily for trend analysis.",
                },
                {
                    "model": "AnalyticsDataService",
                    "table": "statistics.analytics_service",
                    "scope": "application_cache",
                    "notes": "Cached global inventory analytics payloads consumed by developer dashboards.",
                },
            ],
            metrics=[
                "Quantity on hand, reserved, and available (by unit)",
                "Average lot unit cost and blended inventory value",
                "Days on hand / stock age derived from lots and movement timestamps",
                "Spoilage vs usage rates with freshness efficiency score",
                "Average and extreme unit costs for global benchmarking",
            ],
            dimensions=[
                "organization_id",
                "global_item_id",
                "inventory_item_id",
                "location_id (from UnifiedInventoryHistory)",
                "item_type / inventory_category",
            ],
            events=[
                "inventory_adjusted",
                "inventory_lot_created",
                "inventory_spoilage_recorded",
            ],
            feeds=[
                "FreshnessService snapshots",
                "EventEmitter: inventory metrics",
                "Warehouse ETL for cost distribution",
            ],
            consumers=[
                "Global item stats drawer",
                "Inventory analytics dashboards",
                "Data exports & warehouse fact tables",
            ],
        ),
        CatalogDomain(
            key="batches",
            name="Batch Lifecycle",
            description=(
                "Production planning vs completion metrics, yield, cost variance and "
                "timer durations for every batch."
            ),
            storage=[
                {
                    "model": "Batch",
                    "table": "batch",
                    "scope": "organization",
                    "notes": "Operational batch metadata including status, timestamps and owner.",
                },
                {
                    "model": "BatchStats",
                    "table": "batch_stats",
                    "scope": "organization",
                    "notes": "Planned vs actual efficiency, yield, cost variance, spoilage, duration.",
                },
                {
                    "model": "BatchTimer",
                    "table": "batch_timer",
                    "scope": "organization",
                    "notes": "Task timers for step-level durations (start/stop events).",
                },
                {
                    "model": "RecipeStats",
                    "table": "recipe_stats",
                    "scope": "organization",
                    "notes": "Aggregated success/variance metrics rolled up from batch stats per recipe.",
                },
            ],
            metrics=[
                "Planned vs actual fill efficiency and variance",
                "Yield variance percentage and absolute deltas",
                "Cost variance and total planned/actual batch cost",
                "Batch duration, timer breakdowns, spoilage/waste cost",
                "Recipe success/failure counts linked to batches",
            ],
            dimensions=[
                "organization_id",
                "recipe_id",
                "product_id",
                "location_id (via batch.production_location)",
                "batch_status / failure_reason",
            ],
            events=[
                "batch_started",
                "batch_completed",
                "batch_cancelled",
                "batch_metrics_computed",
            ],
            feeds=[
                "Production planning service",
                "EventEmitter: batch metrics",
                "Warehouse ETL for batch fact table",
            ],
            consumers=[
                "Production dashboards",
                "Recipe-level analytics",
                "Org health reports",
            ],
        ),
        CatalogDomain(
            key="products",
            name="Products & SKUs",
            description=(
                "Finished-good inventory, reservations and SKU cost performance."
            ),
            storage=[
                {
                    "model": "Product",
                    "table": "product",
                    "scope": "organization",
                    "notes": "Canonical product definitions and default attributes.",
                },
                {
                    "model": "ProductVariant",
                    "table": "product_variant",
                    "scope": "organization",
                    "notes": "Variant-specific data for pack sizes, colors, scents.",
                },
                {
                    "model": "ProductSKU",
                    "table": "product_sku",
                    "scope": "organization",
                    "notes": "Sellable SKUs linking to inventory items and reservation availability.",
                },
                {
                    "model": "Reservation",
                    "table": "reservation",
                    "scope": "organization",
                    "notes": "Open reservations for orders and channel allocations.",
                },
            ],
            metrics=[
                "On-hand vs reserved quantities per SKU",
                "Velocity (reservations + batches produced)",
                "Unit cost roll-ups from linked inventory lots",
                "Stock alerts vs low-threshold breaches",
            ],
            dimensions=[
                "organization_id",
                "product_type",
                "sku_id",
                "channel / reservation_type",
                "location_id (when tied to fulfillment site)",
            ],
            events=[
                "product_created",
                "product_variant_created",
                "sku_created",
                "reservation_created",
            ],
            feeds=[
                "ReservationService summaries",
                "Inventory adjustments (for finished goods)",
            ],
            consumers=[
                "Sales planning",
                "SKU reservation drawer",
                "Catalog exports",
            ],
        ),
        CatalogDomain(
            key="global_items",
            name="Global Item Library Adoption",
            description=(
                "Cross-tenant adoption metrics, cost curves and data quality gaps for the "
                "public global item catalog."
            ),
            storage=[
                {
                    "model": "GlobalItem",
                    "table": "global_item",
                    "scope": "global",
                    "notes": "Canonical item definitions with density/capacity metadata and cosmetic chemistry fields.",
                },
                {
                    "model": "InventoryItem",
                    "table": "inventory_item",
                    "scope": "organization",
                    "notes": "Linkage via global_item_id for adoption counts and quality checks.",
                },
                {
                    "model": "GlobalItemStatsService",
                    "table": "(computed)",
                    "scope": "aggregate",
                    "notes": "Derived rollups for cost distribution, stock age, expired quantities.",
                },
                {
                    "model": "AnalyticsDataService",
                    "table": "statistics.analytics_service",
                    "scope": "application_cache",
                    "notes": "Service endpoints feeding global item sidebar and inventory analytics UI.",
                },
            ],
            metrics=[
                "Number of org-linked inventory items per global item",
                "Missing density/capacity/shelf-life completeness score",
                "Average unit cost distribution (min/mean/high, outliers)",
                "Average days-to-usage vs days-past-expiration",
            ],
            dimensions=[
                "global_item_id",
                "organization_id",
                "item_type",
                "ingredient_category_id",
            ],
            events=[
                "global_item_created",
                "global_item_archived",
                "global_item_deleted",
            ],
            feeds=[
                "Global library public API",
                "Developer global item drawer",
                "Warehouse dimensional tables",
            ],
            consumers=[
                "Analytics catalog",
                "Inventory onboarding",
                "Pricing benchmark reports",
            ],
        ),
        CatalogDomain(
            key="people",
            name="Users & Workforce",
            description=(
                "User activity, batch participation, production timer and retention metrics."
            ),
            storage=[
                {
                    "model": "User",
                    "table": "user",
                    "scope": "organization",
                    "notes": "Core identity, role mapping and org membership.",
                },
                {
                    "model": "UserStats",
                    "table": "user_stats",
                    "scope": "organization",
                    "notes": "Cached totals for batches, recipes, inventory adjustments, products created.",
                },
                {
                    "model": "RetentionSnapshot",
                    "table": "retention_snapshot",
                    "scope": "organization",
                    "notes": "Churn cohort data powering retention drawers.",
                },
                {
                    "model": "AnalyticsDataService",
                    "table": "statistics.analytics_service",
                    "scope": "application_cache",
                    "notes": "System dashboards aggregating user and workforce metrics.",
                },
            ],
            metrics=[
                "Total / active users per organization",
                "Batches per user, completion rate, failure counts",
                "Inventory adjustments initiated per user",
                "Timer utilization and task duration distributions",
            ],
            dimensions=[
                "organization_id",
                "user_id",
                "role / permission",
                "location_id (when derived from batch participation)",
            ],
            events=[
                "user_invited",
                "user_activated",
                "user_deactivated",
            ],
            feeds=[
                "Waitlist & onboarding funnels",
                "Retention Drawer protocol",
            ],
            consumers=[
                "Org health scores",
                "Leaderboards",
                "Billing seat usage",
            ],
        ),
        CatalogDomain(
            key="organizations",
            name="Organizations & Tenancy",
            description=(
                "Aggregated KPIs per organization including batch throughput, product counts and billing status."
            ),
            storage=[
                {
                    "model": "Organization",
                    "table": "organization",
                    "scope": "global",
                    "notes": "Tenant metadata, subscription tier and lifecycle state.",
                },
                {
                    "model": "OrganizationStats",
                    "table": "organization_stats",
                    "scope": "global",
                    "notes": "Cached totals for batches, users, recipes, inventory value.",
                },
                {
                    "model": "OrganizationLeaderboardStats",
                    "table": "organization_leaderboard_stats",
                    "scope": "global",
                    "notes": "Derived leaderboard metrics for multi-tenant comparisons.",
                },
                {
                    "model": "AnalyticsDataService",
                    "table": "statistics.analytics_service",
                    "scope": "application_cache",
                    "notes": "Developer and organization dashboards with cached KPIs.",
                },
            ],
            metrics=[
                "Total / active organizations by tier",
                "Completed / failed / cancelled batch totals",
                "Inventory value and product catalog breadth",
                "Seat utilization vs tier limits",
                "Billing status (active, past_due, suspended)",
            ],
            dimensions=[
                "organization_id",
                "subscription_tier_id",
                "region / locale",
                "industry tags",
            ],
            events=[
                "organization_created",
                "subscription_tier_changed",
                "organization_suspended",
            ],
            feeds=[
                "BillingService",
                "System statistics dashboard",
            ],
            consumers=[
                "Developer dashboard",
                "Growth reporting",
                "Feature-flag targeting",
            ],
        ),
        CatalogDomain(
            key="system",
            name="System Telemetry & Faults",
            description=(
                "Platform-wide logs, domain events, drawer interactions and fault reports for operations analytics."
            ),
            storage=[
                {
                    "model": "DomainEvent",
                    "table": "domain_event",
                    "scope": "global",
                    "notes": "Immutable audit/event stream with correlation IDs for warehouse ingestion.",
                },
                {
                    "model": "FaultLog",
                    "table": "fault_log",
                    "scope": "global",
                    "notes": "Captured errors surfaced via fault log drawer with metadata and resolution status.",
                },
                {
                    "model": "DrawerRequest",
                    "table": "drawer_request",
                    "scope": "global",
                    "notes": "DrawerProtocol events for open/continue/dismiss instrumentation.",
                },
                {
                    "model": "AppSetting",
                    "table": "app_setting",
                    "scope": "config",
                    "notes": "Runtime settings payloads for alerts, marketing, and waitlists.",
                },
                {
                    "model": "FeatureFlag",
                    "table": "feature_flag",
                    "scope": "config",
                    "notes": "Feature flag switches persisted in the database for runtime checks.",
                },
            ],
            metrics=[
                "Event volume by domain and severity",
                "Drawer completion funnels (open → continue → submit)",
                "Fault rate per feature flag / release",
                "API usage (rate limiter hits, latency windows)",
            ],
            dimensions=[
                "event_name",
                "feature_flag",
                "organization_id",
                "location_id",
                "client version / platform",
            ],
            events=[
                "drawer_opened",
                "drawer_completed",
                "fault_logged",
                "feature_flag_toggled",
            ],
            feeds=[
                "DrawerProtocol instrumentation",
                "Limiter metrics",
                "External monitoring hooks",
            ],
            consumers=[
                "Developer audit tools",
                "Operations runbooks",
                "Reliability dashboards",
            ],
        ),
    ]

    @classmethod
    def get_domains(cls) -> List[Dict[str, Any]]:
        """Return a deep-copied list of catalog domains suitable for templates."""

        try:
            return [copy.deepcopy(domain.__dict__) for domain in cls._DOMAINS]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Suppressed exception fallback at app/services/statistics/catalog.py:494", exc_info=True)
            raise AnalyticsCatalogError("Failed to build analytics catalog") from exc

    @classmethod
    def get_domain(cls, key: str) -> Optional[Dict[str, Any]]:
        """Lookup a single catalog domain by key."""

        for domain in cls._DOMAINS:
            if domain.key == key:
                return copy.deepcopy(domain.__dict__)
        return None

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        """High-level metadata used for the catalog header."""

        return {
            "version": cls._CATALOG_VERSION,
            "updated_at": cls._UPDATED_AT,
            "domain_count": len(cls._DOMAINS),
            "domain_keys": [domain.key for domain in cls._DOMAINS],
        }


__all__ = ["AnalyticsCatalogService", "AnalyticsCatalogError", "CatalogDomain"]
