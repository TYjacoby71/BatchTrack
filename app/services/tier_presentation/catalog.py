"""Tier presentation rule catalog.

Synopsis:
Defines customer-facing comparison sections and highlight rules for plan pages.

Glossary:
- Section: Logical group of rows shown in a comparison table.
- Rule: Declarative entitlement predicate used to render a feature row.
"""

from __future__ import annotations

from typing import Any


FEATURE_COMPARISON_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "title": "Core workflow features",
        "rows": (
            {
                "label": "Inventory management (logging, adjustments, cost visibility)",
                "kind": "boolean",
                "permissions_any": (
                    "inventory.edit",
                    "inventory.adjust",
                    "inventory.view_costs",
                ),
            },
            {
                "label": "FIFO lot tracking and traceability",
                "kind": "boolean",
                "permissions_any": ("inventory.view",),
            },
            {
                "label": "Recipe management and scaling",
                "kind": "boolean",
                "permissions_any": ("recipes.create", "recipes.edit", "recipes.scale"),
            },
            {
                "label": "Production planning",
                "kind": "boolean",
                "permissions_any": ("recipes.plan_production",),
            },
            {
                "label": "Batch production workflow",
                "kind": "boolean",
                "permissions_any": ("batches.create", "batches.finish"),
            },
            {
                "label": "Product catalog and SKU workflows",
                "kind": "boolean",
                "permissions_any": ("products.create", "products.manage_variants"),
            },
            {
                "label": "Recipe variation workflows",
                "kind": "boolean",
                "permissions_any": ("recipes.create_variations",),
                "addon_keys_any": ("recipe_variations",),
            },
        ),
    },
    {
        "title": "Growth and channel features",
        "rows": (
            {
                "label": "Recipe Library and Marketplace publishing",
                "kind": "boolean",
                "permissions_any": (
                    "recipes.marketplace_dashboard",
                    "recipes.sharing_controls",
                ),
            },
            {
                "label": "Paid recipe purchase controls",
                "kind": "boolean",
                "permissions_any": ("recipes.purchase_options",),
            },
            {
                "label": "Global Inventory Library import",
                "kind": "boolean",
                "permissions_any": ("inventory.edit",),
            },
            {
                "label": "Public maker tools (soap, candle, lotion, herbal, baking)",
                "kind": "text",
                "text": "Included for all visitors",
            },
            {
                "label": "Shopify / marketplace / API integrations",
                "kind": "boolean",
                "permissions_any": (
                    "integrations.shopify",
                    "integrations.marketplace",
                    "integrations.api_access",
                ),
            },
            {
                "label": "Bulk inventory updates",
                "kind": "boolean",
                "permissions_any": ("inventory.adjust",),
            },
            {
                "label": "Bulk production stock checks",
                "kind": "boolean",
                "permissions_any": ("recipes.plan_production",),
            },
        ),
    },
    {
        "title": "AI, team, and governance",
        "rows": (
            {
                "label": "BatchBot assistant",
                "kind": "boolean",
                "permissions_any": ("ai.batchbot",),
                "addon_keys_any": ("batchbot_access",),
            },
            {
                "label": "Advanced analytics suite",
                "kind": "boolean",
                "permissions_any": ("reports.advanced", "reports.custom", "reports.analytics"),
                "addon_keys_any": ("advanced_analytics",),
            },
            {
                "label": "Organization dashboard",
                "kind": "boolean",
                "permissions_any": ("organization.view",),
            },
            {
                "label": "Team member management",
                "kind": "boolean",
                "permissions_any": ("organization.manage_users",),
                "min_user_limit": 2,
            },
            {
                "label": "Role and permission management",
                "kind": "boolean",
                "permissions_any": ("organization.manage_roles",),
                "min_user_limit": 2,
            },
            {
                "label": "Billing management",
                "kind": "boolean",
                "permissions_any": ("organization.manage_billing",),
            },
        ),
    },
    {
        "title": "Limits and data policy",
        "rows": (
            {
                "label": "Users per organization",
                "kind": "limit",
                "limit_field": "user_limit",
                "singular": "seat",
                "plural": "seats",
                "none_display": "Contact support",
            },
            {
                "label": "Recipe count",
                "kind": "limit",
                "limit_field": "max_recipes",
                "permissions_any": ("recipes.view", "recipes.create"),
                "singular": "recipe",
                "plural": "recipes",
            },
            {
                "label": "Product count",
                "kind": "limit",
                "limit_field": "max_products",
                "permissions_any": ("products.view", "products.create"),
                "singular": "product",
                "plural": "products",
            },
            {
                "label": "Batch limits",
                "kind": "limit",
                "limit_field": "max_monthly_batches",
                "fallback_field": "max_batches",
                "permissions_any": ("batches.view", "batches.create"),
                "singular": "batch / month",
                "plural": "batches / month",
                "none_display": "Not specified",
            },
            {
                "label": "BatchBot requests per usage window",
                "kind": "batchbot_limit",
            },
            {
                "label": "Data retention policy",
                "kind": "retention",
            },
        ),
    },
)


MAX_MARKETING_HIGHLIGHTS = 8

MARKETING_HIGHLIGHT_RULES: tuple[dict[str, Any], ...] = (
    {
        "label": "Inventory tracking with FIFO lot history",
        "permissions_any": ("inventory.view", "inventory.adjust"),
    },
    {
        "label": "Recipe management, scaling, and production planning",
        "permissions_any": ("recipes.create", "recipes.scale", "recipes.plan_production"),
    },
    {
        "label": "Batch production workflow",
        "permissions_any": ("batches.create", "batches.finish"),
    },
    {
        "label": "Product catalog with SKU and variant support",
        "permissions_any": ("products.create", "products.manage_variants"),
    },
    {
        "label": "Recipe variation workflows",
        "permissions_any": ("recipes.create_variations",),
        "addon_keys_any": ("recipe_variations",),
    },
    {
        "label": "Sales tracking and reservation controls",
        "permissions_any": ("products.sales_tracking", "inventory.reserve"),
    },
    {
        "label": "Team management and role controls",
        "permissions_any": ("organization.manage_users", "organization.manage_roles"),
        "min_user_limit": 2,
    },
    {
        "label": "Recipe Library and marketplace publishing",
        "permissions_any": ("recipes.marketplace_dashboard", "recipes.sharing_controls"),
    },
    {
        "label": "Shopify, marketplace, and API integrations",
        "permissions_any": (
            "integrations.shopify",
            "integrations.marketplace",
            "integrations.api_access",
        ),
    },
    {
        "label": "BatchBot assistant access",
        "permissions_any": ("ai.batchbot",),
        "addon_keys_any": ("batchbot_access",),
    },
    {
        "label": "Data retained while subscribed",
        "require_retention_entitlement": True,
    },
)

