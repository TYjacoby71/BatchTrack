from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import Iterable, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlueprintSpec:
    module: str
    attribute: str
    url_prefix: str | None = None
    description: str | None = None


CORE_BLUEPRINTS: tuple[BlueprintSpec, ...] = (
    BlueprintSpec("app.blueprints.auth", "auth_bp", "/auth", "Authentication"),
    BlueprintSpec("app.blueprints.admin", "admin_bp", "/admin", "Admin"),
    BlueprintSpec("app.blueprints.developer", "developer_bp", "/developer", "Developer"),
    BlueprintSpec("app.blueprints.inventory", "inventory_bp", "/inventory", "Inventory"),
    BlueprintSpec("app.blueprints.recipes", "recipes_bp", "/recipes", "Recipes"),
    BlueprintSpec("app.blueprints.batches", "batches_bp", "/batches", "Batches"),
    BlueprintSpec("app.blueprints.organization.routes", "organization_bp", "/organization", "Organization"),
    BlueprintSpec("app.blueprints.billing", "billing_bp", "/billing", "Billing"),
    BlueprintSpec("app.blueprints.onboarding.routes", "onboarding_bp", "/onboarding", "Onboarding"),
    BlueprintSpec("app.blueprints.settings", "settings_bp", "/settings", "Settings"),
    BlueprintSpec("app.blueprints.timers", "timers_bp", "/timers", "Timers"),
    BlueprintSpec("app.blueprints.expiration", "expiration_bp", "/expiration", "Expiration"),
    BlueprintSpec("app.blueprints.conversion", "conversion_bp", "/conversion", "Conversion"),
    BlueprintSpec("app.blueprints.production_planning", "production_planning_bp", "/production-planning", "Production Planning"),
)

API_BLUEPRINTS: tuple[BlueprintSpec, ...] = (
    BlueprintSpec("app.blueprints.api.public", "public_api_bp", "/api/public", "Public API"),
    BlueprintSpec("app.blueprints.api.routes", "api_bp", "/api", "Main API"),
    BlueprintSpec("app.blueprints.api.drawers", "drawers_bp", None, "Drawer API"),
)

ROUTE_BLUEPRINTS: tuple[BlueprintSpec, ...] = (
    BlueprintSpec("app.routes.app_routes", "app_routes_bp", None, "App Routes"),
    BlueprintSpec("app.routes.pricing_routes", "pricing_bp", None, "Pricing Routes"),
    BlueprintSpec("app.routes.landing_routes", "landing_pages_bp", None, "Landing Pages"),
    BlueprintSpec("app.routes.legal_routes", "legal_bp", "/legal", "Legal Routes"),
    BlueprintSpec("app.routes.bulk_stock_routes", "bulk_stock_bp", "/bulk-stock", "Bulk Stock"),
    BlueprintSpec("app.routes.fault_log_routes", "faults_bp", "/faults", "Fault Log"),
    BlueprintSpec("app.routes.tag_manager_routes", "tag_manager_bp", "/tag-manager", "Tag Manager"),
    BlueprintSpec("app.routes.global_library_routes", "global_library_bp", None, "Global Library"),
    BlueprintSpec("app.routes.recipe_library_routes", "recipe_library_bp", None, "Recipe Library"),
    BlueprintSpec("app.routes.waitlist_routes", "waitlist_bp", None, "Waitlist"),
    BlueprintSpec("app.routes.help_routes", "help_bp", None, "Help & Instructions"),
    BlueprintSpec("app.routes.tools_routes", "tools_bp", "/tools", "Public Tools"),
)

EXTRA_BLUEPRINTS: tuple[BlueprintSpec, ...] = (
    BlueprintSpec("app.routes.exports_routes", "exports_bp", "/exports", "Exports"),
)

BLUEPRINT_SPECS: tuple[BlueprintSpec, ...] = CORE_BLUEPRINTS + API_BLUEPRINTS + ROUTE_BLUEPRINTS + EXTRA_BLUEPRINTS

CSRF_EXEMPT_VIEWS: tuple[str, ...] = (
    "inventory.adjust_inventory",
    "inventory.api_bulk_inventory_adjustments",
    "waitlist.join_waitlist",
    # Public vendor lead capture endpoint is anonymous by design.
    "app_routes.vendor_signup",
    # Public compute endpoint is read-only and used by anonymous tool visitors.
    "tools_bp.tools_soap_calculate",
    "tools_bp.tools_draft",
)


def register_blueprints(app) -> None:
    """Safely register all application blueprints."""

    successes: List[str] = []
    failures: List[str] = []

    for spec in BLUEPRINT_SPECS:
        _safe_register_blueprint(app, spec, successes, failures)

    _register_products(app, successes, failures)
    _log_summary(app, successes, failures)
    _apply_csrf_exemptions(app)


def _safe_register_blueprint(app, spec: BlueprintSpec, successes: List[str], failures: List[str]) -> bool:
    try:
        module = import_module(spec.module)
        blueprint = getattr(module, spec.attribute)
        if spec.url_prefix:
            app.register_blueprint(blueprint, url_prefix=spec.url_prefix)
        else:
            app.register_blueprint(blueprint)
        successes.append(spec.description or spec.attribute)
        return True
    except Exception as exc:  # pragma: no cover - defensive
        failures.append(f"{spec.description or spec.attribute}: {exc}")
        return False


def _register_products(app, successes: List[str], failures: List[str]) -> None:
    try:
        from app.blueprints.products import register_product_blueprints

        register_product_blueprints(app)
        successes.append("Products")
    except Exception as exc:
        failures.append(f"Products: {exc}")
        try:
            from app.blueprints.products.products import products_bp

            app.register_blueprint(products_bp)
            successes.append("Products Fallback")
        except Exception as fallback_exc:  # pragma: no cover
            failures.append(f"Products Fallback: {fallback_exc}")


def _log_summary(app, successes: List[str], failures: List[str]) -> None:
    app_logger = getattr(app, "logger", logger)
    if not (app.debug or failures):
        return

    app_logger.info("=== Blueprint Registration Summary ===")
    app_logger.info("Successful: %s", len(successes))
    if app.debug:
        for name in successes:
            app_logger.info("  - %s", name)

    if failures:
        app_logger.error("Failed: %s", len(failures))
        for failure in failures:
            app_logger.error("  - %s", failure)
    else:
        app_logger.info("All blueprints registered successfully.")


def _apply_csrf_exemptions(app) -> None:
    try:
        from .extensions import csrf
    except Exception:
        return

    for view_name in CSRF_EXEMPT_VIEWS:
        view = app.view_functions.get(view_name)
        if view:
            try:
                csrf.exempt(view)
            except Exception:
                continue