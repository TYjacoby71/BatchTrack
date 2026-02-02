from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app

from app.utils.json_store import write_json_file
from app.utils.settings import get_settings, save_settings


FEATURE_FLAG_SECTIONS: List[Dict[str, Any]] = [
    {
        "title": "Core business features",
        "description": "Enable or disable the production features that every organization depends on.",
        "flags": [
            {
                "key": "FEATURE_FIFO_TRACKING",
                "label": "FIFO Inventory Tracking",
                "status": "standard",
                "toggle": False,
                "always_on": True,
                "default_enabled": True,
                "description": "Standard FIFO behavior baked into inventory adjustments (always on).",
            },
            {
                "key": "FEATURE_BARCODE_SCANNING",
                "label": "Barcode Scanning",
                "status": "stub",
                "default_enabled": False,
                "description": "Placeholder for future scanner integrations.",
            },
            {
                "key": "FEATURE_PRODUCT_VARIANTS",
                "label": "Product Variants System",
                "status": "standard",
                "toggle": False,
                "always_on": True,
                "default_enabled": True,
                "description": "Variant-ready product catalog (always on).",
            },
            {
                "key": "FEATURE_AUTO_SKU_GENERATION",
                "label": "Auto-generate SKUs",
                "status": "standard",
                "toggle": False,
                "always_on": True,
                "default_enabled": True,
                "description": "SKU generation is part of product creation (always on).",
            },
            {
                "key": "FEATURE_COST_TRACKING",
                "label": "Cost Tracking & Profit Margins",
                "status": "standard",
                "toggle": False,
                "always_on": True,
                "default_enabled": True,
                "description": "Core costing engine and margin calculations (always on).",
            },
            {
                "key": "FEATURE_EXPIRATION_TRACKING",
                "label": "Expiration Date Tracking",
                "status": "standard",
                "toggle": False,
                "always_on": True,
                "default_enabled": True,
                "description": "Lot-based expiration handling (always on).",
            },
            {
                "key": "FEATURE_BULK_STOCK_CHECK",
                "label": "Bulk Stock Check",
                "status": "wired",
                "default_enabled": False,
                "description": "Multi-recipe stock check and shopping list exports.",
            },
            {
                "key": "FEATURE_BULK_INVENTORY_UPDATES",
                "label": "Bulk Inventory Updates",
                "status": "wired",
                "default_enabled": False,
                "description": "Bulk inventory adjustments and high-volume update tooling.",
            },
        ],
    },
    {
        "title": "Developer & advanced features",
        "description": "Capabilities intended for internal tooling or staging environments.",
        "flags": [
            {
                "key": "FEATURE_MERGE_SKUS",
                "label": "Merge SKUs",
                "status": "wired",
                "default_enabled": True,
                "description": "Merge multiple SKUs into a single consolidated SKU.",
            },
            {
                "key": "FEATURE_AUTO_BULK_SKU_ON_VARIANT",
                "label": "Auto-create Bulk SKU on Variant",
                "status": "wired",
                "default_enabled": False,
                "description": "Require a unit and create a Bulk SKU when adding a variant.",
            },
            {
                "key": "FEATURE_CSV_EXPORT",
                "label": "CSV Export",
                "status": "wired",
                "default_enabled": False,
                "description": "Downloadable CSV exports for reports.",
            },
            {
                "key": "FEATURE_ADVANCED_REPORTS",
                "label": "Advanced Reports",
                "status": "stub",
                "default_enabled": False,
                "description": "Future premium reporting suite.",
            },
            {
                "key": "FEATURE_GLOBAL_ITEM_LIBRARY",
                "label": "Global Item Library Access",
                "status": "wired",
                "default_enabled": True,
                "description": "Org access to the shared global inventory library.",
            },
        ],
    },
    {
        "title": "Organization administration",
        "description": "Controls for organization-level management tooling.",
        "flags": [
            {
                "key": "FEATURE_ORG_ROLE_MANAGEMENT",
                "label": "Role Management Tab",
                "status": "wired",
                "default_enabled": True,
                "description": "Show the Role Management tab on the organization dashboard.",
            },
        ],
    },
    {
        "title": "Commerce & POS integrations",
        "description": "Stubbed flags for future ecommerce and POS entry points.",
        "flags": [
            {
                "key": "FEATURE_ECOMMERCE_INTEGRATIONS",
                "label": "E-commerce Integration Hub",
                "status": "stub",
                "default_enabled": False,
                "description": "Gate the entry point for ecommerce integration workflows.",
            },
            {
                "key": "FEATURE_SHOPIFY_INTEGRATION",
                "label": "Shopify Integration",
                "status": "stub",
                "default_enabled": False,
                "description": "Stub for Shopify integration surfaces.",
            },
            {
                "key": "FEATURE_ETSY_INTEGRATION",
                "label": "Etsy Integration",
                "status": "stub",
                "default_enabled": False,
                "description": "Stub for Etsy marketplace integration surfaces.",
            },
        ],
    },
    {
        "title": "Recipe Library & Marketplace",
        "description": "Controls for sharing recipes publicly and exposing the marketplace surface.",
        "flags": [
            {
                "key": "FEATURE_RECIPE_LIBRARY_NAV",
                "label": "Recipe Library Navigation",
                "status": "wired",
                "default_enabled": False,
                "description": "Expose the public recipe library link in customer menus.",
            },
            {
                "key": "FEATURE_RECIPE_MARKETPLACE_DISPLAY",
                "label": "Recipe Marketplace Display",
                "status": "wired",
                "default_enabled": True,
                "description": "Show marketplace pages, purchase buttons, and org marketplace links.",
            },
            {
                "key": "FEATURE_RECIPE_MARKETPLACE_LISTINGS",
                "label": "Recipe Listing Controls",
                "status": "wired",
                "default_enabled": True,
                "description": "Allow listing controls inside the recipe edit experience.",
            },
        ],
    },
    {
        "title": "AI & forecasting experiments",
        "description": "Aspirational features that are not yet implemented.",
        "flags": [
            {
                "key": "FEATURE_AI_RECIPE_OPTIMIZATION",
                "label": "AI Recipe Optimization",
                "status": "stub",
                "default_enabled": False,
                "description": "ML-assisted formulation suggestions.",
            },
            {
                "key": "FEATURE_AI_DEMAND_FORECASTING",
                "label": "AI Demand Forecasting",
                "status": "stub",
                "default_enabled": False,
                "description": "Predict demand to guide purchasing.",
            },
            {
                "key": "FEATURE_AI_QUALITY_INSIGHTS",
                "label": "AI Quality Insights",
                "status": "stub",
                "default_enabled": False,
                "description": "Automated quality checks & anomaly detection.",
            },
        ],
    },
    {
        "title": "Public tool availability",
        "description": "Control which calculator suites are exposed on the marketing site.",
        "flags": [
            {
                "key": "TOOLS_SOAP",
                "label": "Soap Making Tools",
                "status": "wired",
                "default_enabled": True,
                "description": "Saponification & curing calculators.",
            },
            {
                "key": "TOOLS_SOAP_CSV_PRIMARY",
                "label": "Soap Tool CSV Primary Lookup",
                "status": "wired",
                "default_enabled": True,
                "description": "Use CSV-backed soapcalc data first (fallback to GIL).",
            },
            {
                "key": "TOOLS_CANDLES",
                "label": "Candle Making Tools",
                "status": "wired",
                "default_enabled": True,
                "description": "Wick, wax, and fragrance load calculators.",
            },
            {
                "key": "TOOLS_LOTIONS",
                "label": "Lotion & Cosmetic Tools",
                "status": "wired",
                "default_enabled": True,
                "description": "Batch math for cosmetics and topicals.",
            },
            {
                "key": "TOOLS_HERBAL",
                "label": "Herbalist Tools",
                "status": "wired",
                "default_enabled": True,
                "description": "Tincture and infusion helpers.",
            },
            {
                "key": "TOOLS_BAKING",
                "label": "Baking Tools",
                "status": "wired",
                "default_enabled": True,
                "description": "Recipe scaling for bakers & confectioners.",
            },
        ],
    },
]


BATCHLEY_JOB_CATALOG: List[Dict[str, Any]] = [
    {
        "slug": "recipe-intake",
        "name": "Recipe Draft Intake",
        "tool": "create_recipe_draft",
        "status": "wired",
        "description": "Uploads text (and OCR’d images) to create missing inventory items first, then saves the recipe as a draft with granular success messaging.",
        "inputs": [
            "Text instructions, ingredient lists, or OCR payloads",
            "Optional yield amount/unit for scaling",
            "Ingredient rows with allow_create toggles",
        ],
        "outputs": [
            "New inventory items seeded before the recipe",
            "Recipe draft saved for manual review/publish",
            "Partial failure report when a single ingredient needs correction",
        ],
        "handoff": "Draft stays unpublished until a human reviews and publishes the recipe.",
    },
    {
        "slug": "bulk-inventory",
        "name": "Bulk Inventory Receipt Builder",
        "tool": "submit_bulk_inventory_update",
        "status": "wired",
        "description": "Parses messy receipts or free-form shopping lists, asks for clarifications, and stages create/restock/spoil/trash rows in the bulk modal.",
        "inputs": [
            "Receipt text or photo transcription (quantities + units)",
            "Desired change_type per row (create/restock/spoil/trash)",
            "Optional cost overrides and notes",
        ],
        "outputs": [
            "Draft bulk adjustment queued for user confirmation",
            "Ability to auto-submit when customer explicitly asks",
            "Row-level audit trail posted back to the chat transcript",
        ],
        "handoff": "Customer can edit/save drafts in the modal before the final submit call.",
    },
    {
        "slug": "single-restock",
        "name": "Single Item Restock",
        "tool": "log_inventory_purchase",
        "status": "wired",
        "description": "Fast path for topping up one inventory item when the user already knows the SKU.",
        "inputs": [
            "Inventory item ID or fuzzy name match",
            "Quantity + unit, optional cost per unit",
            "Free-form note for receipt/source",
        ],
        "outputs": [
            "Inventory adjustment entry with costing metadata",
            "Follow-up prompt offering FIFO/expiration guidance",
        ],
        "handoff": "Ideal for “I just restocked olive oil” requests—no modal required.",
    },
    {
        "slug": "insights",
        "name": "Insight Snapshot / KPI Q&A",
        "tool": "fetch_insight_snapshot",
        "status": "wired",
        "description": "Returns costing, freshness, throughput, and global benchmark snippets that Batchley can narrate back to the user.",
        "inputs": [
            "Optional focus flag: cost, freshness, throughput, overview",
        ],
        "outputs": [
            "Structured JSON (org dashboard, hotspots, freshness risks)",
            "Comparative guidance vs global averages",
        ],
        "handoff": "Often paired with coaching copy or follow-up prompts to gather more context.",
    },
    {
        "slug": "marketplace",
        "name": "Marketplace Sync Check",
        "tool": "fetch_marketplace_status",
        "status": "beta",
        "description": "Surfaces recipe marketplace readiness, pending syncs, and recent failures so support can respond inside the chat.",
        "inputs": [
            'Optional "limit" to cap how many listings to summarize (default 5)',
        ],
        "outputs": [
            "Counts for total/pending/failed listings",
            "Top product cards with last sync timestamp + status",
        ],
        "handoff": "Hidden unless the org tier has marketplace permissions.",
    },
]


BATCHLEY_ENV_KEYS: List[Dict[str, Any]] = [
    {
        "key": "GOOGLE_AI_API_KEY",
        "label": "Google AI API Key",
        "description": "Gemini credential for both Batchley and the public help bot.",
        "secret": True,
    },
    {
        "key": "GOOGLE_AI_BATCHBOT_MODEL",
        "label": "Batchley Model",
        "description": "Model override for authenticated Batchley traffic.",
    },
    {
        "key": "GOOGLE_AI_PUBLICBOT_MODEL",
        "label": "Public Bot Model",
        "description": "Model used on the marketing site/public help modal.",
    },
    {
        "key": "BATCHBOT_DEFAULT_MAX_REQUESTS",
        "label": "Default Action Cap",
        "description": "Base automation quota per org per window (tiers override).",
    },
    {
        "key": "BATCHBOT_CHAT_MAX_MESSAGES",
        "label": "Default Chat Cap",
        "description": "Baseline chat-only prompts per window.",
    },
    {
        "key": "BATCHBOT_REQUEST_WINDOW_DAYS",
        "label": "Usage Window (days)",
        "description": "Length of the rolling window for action/chat quotas.",
    },
    {
        "key": "BATCHBOT_SIGNUP_BONUS_REQUESTS",
        "label": "Signup Bonus Credits",
        "description": "Promo requests granted to new organizations.",
    },
    {
        "key": "BATCHBOT_REFILL_LOOKUP_KEY",
        "label": "Stripe Refill Lookup Key",
        "description": "Price lookup key referenced when issuing refill checkout sessions.",
    },
    {
        "key": "BATCHBOT_COST_PER_MILLION_INPUT",
        "label": "Cost Per Million Input Tokens",
        "description": "Reference compute cost for per-token pricing.",
        "format": "currency",
    },
    {
        "key": "BATCHBOT_COST_PER_MILLION_OUTPUT",
        "label": "Cost Per Million Output Tokens",
        "description": "Reference compute cost for responses.",
        "format": "currency",
    },
]


BATCHLEY_WORKFLOW_NOTES: List[Dict[str, str]] = [
    {
        "title": "Session-bound execution",
        "body": "Batchley refuses to run without an authenticated organization user, so every automation inherits the same RBAC + tier limits as the UI.",
    },
    {
        "title": "Chat vs action metering",
        "body": "Pure Q&A consumes the chat bucket; tool calls consume the action bucket and will automatically recommend the refill checkout URL when exhausted.",
    },
    {
        "title": "Draft-first UX",
        "body": "Recipe creation and bulk inventory flows always build drafts so humans can confirm edits before publishing. Partial failures are spelled out in the response payload.",
    },
    {
        "title": "Marketplace awareness",
        "body": "Marketplace tooling only activates for tiers that include `integrations.marketplace`, preventing leakage for customers without licensing.",
    },
]


@dataclass(frozen=True)
class BatchleyContext:
    job_catalog: List[Dict[str, Any]]
    env_status: List[Dict[str, Any]]
    limit_cards: List[Dict[str, str]]
    workflow_notes: List[Dict[str, str]]


class DeveloperDashboardService:
    """Service helpers backing the developer dashboard experience."""

    @staticmethod
    def build_dashboard_context(force_refresh: bool = False) -> Dict[str, Any]:
        from app.services.statistics import AnalyticsDataService

        dashboard_data = AnalyticsDataService.get_developer_dashboard(
            force_refresh=force_refresh
        )
        overview = dashboard_data.get("overview") or {}
        tier_breakdown = overview.get("tiers") or {}
        recent_orgs = dashboard_data.get("recent_organizations") or []
        problem_orgs = dashboard_data.get("attention_organizations") or []
        waitlist_count = dashboard_data.get("waitlist_count", 0)
        new_orgs_count = dashboard_data.get("recent_count") or len(recent_orgs)
        attention_count = dashboard_data.get("attention_count") or len(problem_orgs)
        fault_feed = AnalyticsDataService.get_fault_log_entries(
            include_all=True, force_refresh=force_refresh
        )
        support_queue = fault_feed[:4]
        support_queue_total = len(fault_feed)

        generated_iso = dashboard_data.get("generated_at")
        generated_display = DeveloperDashboardService._format_generated_at(generated_iso)

        return {
            "total_orgs": overview.get("total_organizations", 0),
            "active_orgs": overview.get("active_organizations", 0),
            "total_users": overview.get("total_users", 0),
            "active_users": overview.get("active_users", 0),
            "new_orgs_count": new_orgs_count,
            "attention_count": attention_count,
            "tier_breakdown": tier_breakdown,
            "recent_orgs": recent_orgs,
            "problem_orgs": problem_orgs,
            "support_queue": support_queue,
            "support_queue_total": support_queue_total,
            "waitlist_count": waitlist_count,
            "dashboard_generated_at": generated_display,
        }

    @staticmethod
    def get_marketing_admin_context() -> Dict[str, Any]:
        from app.services.statistics import AnalyticsDataService

        marketing_data = AnalyticsDataService.get_marketing_content()
        reviews = marketing_data.get("reviews", [])
        spotlights = marketing_data.get("spotlights", [])
        messages = {"day_1": "", "day_3": "", "day_5": ""}
        messages.update(marketing_data.get("marketing_messages", {}))
        promo_codes = marketing_data.get("promo_codes", []) or []
        demo_url = marketing_data.get("demo_url", "") or ""
        demo_videos = marketing_data.get("demo_videos", []) or []
        return {
            "reviews": reviews,
            "spotlights": spotlights,
            "messages": messages,
            "promo_codes": promo_codes,
            "demo_url": demo_url,
            "demo_videos": demo_videos,
        }

    @staticmethod
    def save_marketing_payload(payload: Dict[str, Any]) -> None:
        if "reviews" in payload:
            write_json_file("data/reviews.json", payload["reviews"])
        if "spotlights" in payload:
            write_json_file("data/spotlights.json", payload["spotlights"])
        if any(
            key in payload
            for key in ("messages", "promo_codes", "demo_url", "demo_videos")
        ):
            cfg = get_settings()
            if "messages" in payload:
                cfg["marketing_messages"] = payload["messages"]
            if "promo_codes" in payload:
                cfg["promo_codes"] = payload["promo_codes"]
            if "demo_url" in payload:
                cfg["demo_url"] = payload["demo_url"]
            if "demo_videos" in payload:
                cfg["demo_videos"] = payload["demo_videos"]
            save_settings(cfg)

    @staticmethod
    def build_batchley_context() -> BatchleyContext:
        env_status: List[Dict[str, Any]] = []

        for entry in BATCHLEY_ENV_KEYS:
            raw_value = current_app.config.get(entry["key"])
            formatted = DeveloperDashboardService._format_env_value(entry, raw_value)
            is_set = raw_value not in (None, "")
            env_status.append(
                {
                    "key": entry["key"],
                    "label": entry["label"],
                    "description": entry["description"],
                    "is_secret": entry.get("secret", False),
                    "is_set": is_set,
                    "value": "Configured" if entry.get("secret") and is_set else formatted,
                }
            )

        limit_cards = [
            {
                "label": "Default action cap / window",
                "value": DeveloperDashboardService._format_limit(
                    current_app.config.get("BATCHBOT_DEFAULT_MAX_REQUESTS"),
                    suffix=" requests",
                ),
                "description": "Used when a subscription tier does not override `max_batchbot_requests` (set -1 for unlimited).",
            },
            {
                "label": "Default chat cap / window",
                "value": DeveloperDashboardService._format_limit(
                    current_app.config.get("BATCHBOT_CHAT_MAX_MESSAGES"),
                    suffix=" messages",
                ),
                "description": "Pure Q&A prompts before Batchley demands either a refill or tier bump (set -1 for unlimited).",
            },
            {
                "label": "Usage window",
                "value": DeveloperDashboardService._format_limit(
                    current_app.config.get("BATCHBOT_REQUEST_WINDOW_DAYS"),
                    suffix=" days",
                ),
                "description": "Defines when counters reset for both chat and action buckets.",
            },
            {
                "label": "Signup bonus credits",
                "value": DeveloperDashboardService._format_limit(
                    current_app.config.get("BATCHBOT_SIGNUP_BONUS_REQUESTS"),
                    suffix=" requests",
                ),
                "description": "Granted per organization immediately after the signup service creates the org.",
            },
            {
                "label": "Stripe refill lookup key",
                "value": current_app.config.get("BATCHBOT_REFILL_LOOKUP_KEY") or "Not set",
                "description": "Must match the price lookup key used by the `batchbot_refill_100` add-on.",
            },
            {
                "label": "Request timeout",
                "value": DeveloperDashboardService._format_limit(
                    current_app.config.get("BATCHBOT_REQUEST_TIMEOUT_SECONDS"),
                    suffix=" seconds",
                ),
                "description": "Raise when Gemini calls might take longer—defaults to 45 seconds.",
            },
            {
                "label": "Cost reference (input tokens)",
                "value": DeveloperDashboardService._format_env_value(
                    {"format": "currency"},
                    current_app.config.get("BATCHBOT_COST_PER_MILLION_INPUT"),
                )
                or "Not set",
                "description": "Used for pricing conversations; update when Google adjusts rates.",
            },
            {
                "label": "Cost reference (output tokens)",
                "value": DeveloperDashboardService._format_env_value(
                    {"format": "currency"},
                    current_app.config.get("BATCHBOT_COST_PER_MILLION_OUTPUT"),
                )
                or "Not set",
                "description": "Pairs with the input rate when modeling gross margin.",
            },
        ]

        return BatchleyContext(
            job_catalog=BATCHLEY_JOB_CATALOG,
            env_status=env_status,
            limit_cards=limit_cards,
            workflow_notes=BATCHLEY_WORKFLOW_NOTES,
        )

    @staticmethod
    def get_feature_flag_sections() -> List[Dict[str, Any]]:
        return FEATURE_FLAG_SECTIONS

    @staticmethod
    def get_toggleable_feature_keys() -> set[str]:
        toggleable: set[str] = set()
        for section in FEATURE_FLAG_SECTIONS:
            for flag in section.get("flags", []):
                if flag.get("toggle", True):
                    toggleable.add(flag["key"])
        return toggleable

    @staticmethod
    def get_waitlist_statistics(force_refresh: bool = False) -> Dict[str, Any]:
        from app.services.statistics import AnalyticsDataService

        return AnalyticsDataService.get_waitlist_statistics(
            force_refresh=force_refresh
        )

    @staticmethod
    def _format_generated_at(generated_iso: Optional[str]) -> Optional[str]:
        if not generated_iso:
            return None
        try:
            generated_dt = datetime.fromisoformat(generated_iso)
            return generated_dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return generated_iso

    @staticmethod
    def _format_env_value(entry: Dict[str, Any], raw_value: Any) -> Optional[str]:
        if raw_value in (None, ""):
            return None
        if entry.get("format") == "currency":
            try:
                return f"${float(raw_value):,.2f}"
            except (TypeError, ValueError):
                return str(raw_value)
        return str(raw_value)

    @staticmethod
    def _format_limit(raw_value: Any, *, suffix: str = "") -> str:
        if raw_value in (None, ""):
            return "Not set"
        try:
            numeric = float(raw_value)
            if numeric < 0:
                return "Unlimited"
            if numeric.is_integer():
                numeric = int(numeric)
            return f"{numeric}{suffix}"
        except (TypeError, ValueError):
            return f"{raw_value}{suffix}"
