"""Analytics event registry.

Synopsis:
Defines the canonical, searchable registry for product analytics event names.
Provides lightweight helpers for validating required properties and grouping
core usage events used by `EventEmitter` enrichment.

Glossary:
- Event spec: Metadata record describing an analytics event contract.
- Core usage event: Event eligible for first/second-use enrichment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalyticsEventSpec:
    """Metadata describing one analytics event contract."""

    name: str
    category: str
    description: str
    required_properties: tuple[str, ...] = ()
    core_usage_event: bool = False


ANALYTICS_EVENT_REGISTRY: dict[str, AnalyticsEventSpec] = {
    # Auth + onboarding + billing funnel
    "user_login_succeeded": AnalyticsEventSpec(
        name="user_login_succeeded",
        category="funnel_auth",
        description="Authenticated login success for an existing user.",
        required_properties=("is_first_login", "login_method", "destination_hint"),
        core_usage_event=True,
    ),
    "signup_completed": AnalyticsEventSpec(
        name="signup_completed",
        category="funnel_signup",
        description="A signup flow created an account (paid or free).",
        required_properties=("signup_source", "signup_flow", "billing_provider"),
        core_usage_event=True,
    ),
    "signup_checkout_started": AnalyticsEventSpec(
        name="signup_checkout_started",
        category="funnel_signup",
        description="Signup flow entered hosted checkout.",
        required_properties=("tier_id", "billing_mode", "billing_cycle"),
        core_usage_event=True,
    ),
    "signup_checkout_completed": AnalyticsEventSpec(
        name="signup_checkout_completed",
        category="funnel_signup",
        description="Hosted checkout completed and signup provisioning succeeded.",
        required_properties=("tier_id", "billing_provider"),
        core_usage_event=True,
    ),
    "purchase_completed": AnalyticsEventSpec(
        name="purchase_completed",
        category="funnel_billing",
        description="Paid checkout completed and account purchase is finalized.",
        required_properties=("tier_id", "billing_provider"),
        core_usage_event=True,
    ),
    "onboarding_completed": AnalyticsEventSpec(
        name="onboarding_completed",
        category="funnel_onboarding",
        description="Onboarding checklist completion for first-session setup.",
        required_properties=("checklist_completed",),
        core_usage_event=True,
    ),
    "billing_checkout_started": AnalyticsEventSpec(
        name="billing_checkout_started",
        category="funnel_billing",
        description="Existing organization initiated a billing upgrade checkout.",
    ),
    "billing.stripe_checkout_completed": AnalyticsEventSpec(
        name="billing.stripe_checkout_completed",
        category="funnel_billing",
        description="Stripe checkout completion marker before signup provisioning events.",
    ),
    # Activation/core usage
    "inventory_item_created": AnalyticsEventSpec(
        name="inventory_item_created",
        category="activation_inventory",
        description="Inventory item created (custom or global).",
        required_properties=("creation_source",),
        core_usage_event=True,
    ),
    "inventory_item_custom_created": AnalyticsEventSpec(
        name="inventory_item_custom_created",
        category="activation_inventory",
        description="Custom inventory item created.",
        required_properties=("creation_source",),
        core_usage_event=True,
    ),
    "inventory_item_global_created": AnalyticsEventSpec(
        name="inventory_item_global_created",
        category="activation_inventory",
        description="Global-catalog inventory item created.",
        required_properties=("creation_source",),
        core_usage_event=True,
    ),
    "recipe_created": AnalyticsEventSpec(
        name="recipe_created",
        category="activation_recipe",
        description="Recipe created (master/variation/test flags included in properties).",
        required_properties=("is_test", "is_variation"),
        core_usage_event=True,
    ),
    "recipe_variation_created": AnalyticsEventSpec(
        name="recipe_variation_created",
        category="activation_recipe",
        description="Recipe variation created.",
        core_usage_event=True,
    ),
    "recipe_test_created": AnalyticsEventSpec(
        name="recipe_test_created",
        category="activation_recipe",
        description="Recipe test version created.",
        core_usage_event=True,
    ),
    "plan_production_requested": AnalyticsEventSpec(
        name="plan_production_requested",
        category="activation_planning",
        description="User requested a production planning run.",
        core_usage_event=True,
    ),
    "stock_check_run": AnalyticsEventSpec(
        name="stock_check_run",
        category="activation_planning",
        description="Stock check executed against a recipe and scale.",
        core_usage_event=True,
    ),
    "batch_started": AnalyticsEventSpec(
        name="batch_started",
        category="activation_batch",
        description="Batch start operation completed.",
        core_usage_event=True,
    ),
    "batch_completed": AnalyticsEventSpec(
        name="batch_completed",
        category="activation_batch",
        description="Batch completion operation finalized.",
        core_usage_event=True,
    ),
    "timer_started": AnalyticsEventSpec(
        name="timer_started",
        category="activation_timer",
        description="Production timer started.",
        core_usage_event=True,
    ),
    # Additional lifecycle events (non-core enrichment by default)
    "inventory_adjusted": AnalyticsEventSpec(
        name="inventory_adjusted",
        category="lifecycle_inventory",
        description="Inventory adjustment applied via standard adjustment path.",
    ),
    "batch_cancelled": AnalyticsEventSpec(
        name="batch_cancelled",
        category="lifecycle_batch",
        description="Batch cancelled and inventory restored.",
    ),
    "batch_failed": AnalyticsEventSpec(
        name="batch_failed",
        category="lifecycle_batch",
        description="Batch marked as failed.",
    ),
    "timer_stopped": AnalyticsEventSpec(
        name="timer_stopped",
        category="lifecycle_timer",
        description="Production timer stopped.",
    ),
    "recipe_updated": AnalyticsEventSpec(
        name="recipe_updated",
        category="lifecycle_recipe",
        description="Recipe updated.",
    ),
    "recipe_deleted": AnalyticsEventSpec(
        name="recipe_deleted",
        category="lifecycle_recipe",
        description="Recipe deleted or archived.",
    ),
    "product_created": AnalyticsEventSpec(
        name="product_created",
        category="lifecycle_product",
        description="Product created.",
    ),
    "product_variant_created": AnalyticsEventSpec(
        name="product_variant_created",
        category="lifecycle_product",
        description="Product variant created.",
    ),
    "sku_created": AnalyticsEventSpec(
        name="sku_created",
        category="lifecycle_product",
        description="SKU created.",
    ),
    "global_item_created": AnalyticsEventSpec(
        name="global_item_created",
        category="lifecycle_global_catalog",
        description="Global catalog item created by developer tooling.",
    ),
    "global_item_deleted": AnalyticsEventSpec(
        name="global_item_deleted",
        category="lifecycle_global_catalog",
        description="Global catalog item deleted or archived.",
    ),
    "batch_metrics_computed": AnalyticsEventSpec(
        name="batch_metrics_computed",
        category="lifecycle_stats",
        description="Batch statistics and freshness metrics computed.",
    ),
}

CORE_USAGE_EVENT_NAMES = frozenset(
    name for name, spec in ANALYTICS_EVENT_REGISTRY.items() if spec.core_usage_event
)


def is_registered_event(event_name: str) -> bool:
    """Return whether an event is present in the canonical registry."""
    return str(event_name or "").strip() in ANALYTICS_EVENT_REGISTRY


def required_properties_for(event_name: str) -> tuple[str, ...]:
    """Return required property names for a registered event."""
    spec = ANALYTICS_EVENT_REGISTRY.get(str(event_name or "").strip())
    if not spec:
        return ()
    return spec.required_properties or ()


def missing_required_properties(event_name: str, properties: dict[str, Any]) -> tuple[str, ...]:
    """Return required properties missing from a candidate payload."""
    required = required_properties_for(event_name)
    if not required:
        return ()
    payload = properties or {}
    missing: list[str] = []
    for key in required:
        if key not in payload:
            missing.append(key)
    return tuple(missing)


def list_registered_events(*, category: str | None = None) -> list[AnalyticsEventSpec]:
    """Return registered event specs sorted by name."""
    specs = list(ANALYTICS_EVENT_REGISTRY.values())
    if category:
        wanted = str(category).strip().lower()
        specs = [spec for spec in specs if spec.category == wanted]
    return sorted(specs, key=lambda spec: spec.name)

