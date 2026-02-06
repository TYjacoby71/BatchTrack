"""Developer integrations checklist views.

Synopsis:
Renders environment readiness and integration diagnostics for developers.

Glossary:
- Checklist: The environment variable matrix shown on the integrations page.
- Section: Grouped config fields within the checklist UI.
"""

from __future__ import annotations

import os
import re

from flask import jsonify, render_template, request
from flask_login import current_user

from app.config import ENV_DIAGNOSTICS
from app.config_schema import build_integration_sections
from app.services.email_service import EmailService
from app.services.developer.dashboard_service import DeveloperDashboardService
from app.services.integrations.registry import build_integration_categories
from app.utils.settings import get_setting, update_settings_value

from ..decorators import require_developer_permission
from ..routes import developer_bp


@developer_bp.route("/integrations")
@require_developer_permission("dev.system_admin")
def integrations_checklist():
    """Comprehensive integrations and launch checklist (developer only)."""
    from flask import current_app
    from app.models.subscription_tier import SubscriptionTier

    def _env_or_config_value(key):
        value = os.environ.get(key)
        if value not in (None, ""):
            return value
        return current_app.config.get(key)

    email_provider = (current_app.config.get("EMAIL_PROVIDER") or "smtp").lower()
    email_configured = EmailService.is_configured()
    email_keys = {
        "SMTP": bool(current_app.config.get("MAIL_SERVER")),
        "SendGrid": bool(current_app.config.get("SENDGRID_API_KEY")),
        "Postmark": bool(current_app.config.get("POSTMARK_SERVER_TOKEN")),
        "Mailgun": bool(
            current_app.config.get("MAILGUN_API_KEY") and current_app.config.get("MAILGUN_DOMAIN")
        ),
    }

    stripe_secret = _env_or_config_value("STRIPE_SECRET_KEY")
    stripe_publishable = _env_or_config_value("STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret = _env_or_config_value("STRIPE_WEBHOOK_SECRET")
    tiers_count = SubscriptionTier.query.count()
    stripe_status = {
        "secret_key_present": bool(stripe_secret),
        "publishable_key_present": bool(stripe_publishable),
        "webhook_secret_present": bool(stripe_webhook_secret),
        "tiers_configured": tiers_count > 0,
    }

    env_core = {
        "app_env": ENV_DIAGNOSTICS.get("active"),
        "source": ENV_DIAGNOSTICS.get("source"),
        "env_variables": ENV_DIAGNOSTICS.get("variables", {}),
        "warnings": ENV_DIAGNOSTICS.get("warnings", ()),
        "SECRET_KEY_present": bool(os.environ.get("FLASK_SECRET_KEY") or current_app.config.get("SECRET_KEY")),
        "LOG_LEVEL": current_app.config.get("LOG_LEVEL", "WARNING"),
    }

    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")

    def _mask_url(value: str) -> str:
        try:
            return re.sub(r"//[^:@/]+:[^@/]+@", "//****:****@", value)
        except Exception:
            return value

    backend = "PostgreSQL" if uri.startswith("postgres") else ("SQLite" if "sqlite" in uri else "Other")
    if "sqlite" in uri:
        source = "fallback"
    elif os.environ.get("DATABASE_URL"):
        source = "DATABASE_URL"
    else:
        source = "config"
    db_info = {
        "uri": _mask_url(uri),
        "backend": backend,
        "source": source,
        "DATABASE_URL_present": bool(os.environ.get("DATABASE_URL")),
    }

    cache_info = {
        "RATELIMIT_STORAGE_URI": current_app.config.get("RATELIMIT_STORAGE_URI", "memory://"),
        "REDIS_URL_present": bool(os.environ.get("REDIS_URL")),
    }

    host_info = {
        "canonical_host": current_app.config.get("CANONICAL_HOST"),
        "external_base_url": current_app.config.get("EXTERNAL_BASE_URL"),
        "preferred_scheme": current_app.config.get("PREFERRED_URL_SCHEME", "https"),
    }

    oauth_status = {
        "GOOGLE_OAUTH_CLIENT_ID_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")),
        "GOOGLE_OAUTH_CLIENT_SECRET_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")),
    }
    whop_status = {
        "WHOP_API_KEY_present": bool(current_app.config.get("WHOP_API_KEY")),
        "WHOP_APP_ID_present": bool(current_app.config.get("WHOP_APP_ID")),
    }

    launch_env_sections = build_integration_sections(
        os.environ,
        ENV_DIAGNOSTICS.get("active", "development"),
    )

    rate_limiters = [
        {
            "endpoint": "GET/POST /auth/login",
            "limit": "100/minute",
            "source": "app/blueprints/auth/routes.py::login",
            "notes": "Primary credential-based login form (scaled for 1K users).",
        },
        {
            "endpoint": "GET /auth/oauth/google",
            "limit": "50/minute",
            "source": "app/blueprints/auth/routes.py::oauth_google",
            "notes": "Google OAuth initiation endpoint.",
        },
        {
            "endpoint": "GET /auth/oauth/callback",
            "limit": "75/minute",
            "source": "app/blueprints/auth/routes.py::oauth_callback",
            "notes": "OAuth callback handler (Google).",
        },
        {
            "endpoint": "GET /auth/callback",
            "limit": "75/minute",
            "source": "app/blueprints/auth/routes.py::oauth_callback_compat",
            "notes": "Legacy alias for the OAuth callback.",
        },
        {
            "endpoint": "GET/POST /auth/signup",
            "limit": "60/minute",
            "source": "app/blueprints/auth/routes.py::signup",
            "notes": "Self-serve signup + tier selection.",
        },
        {
            "endpoint": "GET /",
            "limit": "1000/hour",
            "source": "app/extensions.py::limiter",
            "notes": "Homepage traffic from marketing/SEO.",
        },
        {
            "endpoint": "GET /global-items",
            "limit": "500/hour",
            "source": "app/routes/global_library_routes.py::global_library",
            "notes": "Public global item library browsing.",
        },
        {
            "endpoint": "GET /tools",
            "limit": "800/hour",
            "source": "app/routes/tools_routes.py::tools_index",
            "notes": "Public calculator tools.",
        },
        {
            "endpoint": "GET /recipes/library",
            "limit": "400/hour",
            "source": "app/routes/recipe_library_routes.py::recipe_library",
            "notes": "Public recipe browsing and marketplace.",
        },
        {
            "endpoint": "GET/POST /api/public/*",
            "limit": "200/minute",
            "source": "app/blueprints/api/public.py",
            "notes": "Public API endpoints for global items & unit conversion.",
        },
        {
            "endpoint": "POST /api/drawer-actions/*",
            "limit": "100/minute",
            "source": "app/blueprints/api/drawers/*",
            "notes": "Drawer protocol endpoints for data fixes.",
        },
        {
            "endpoint": "GET/POST /inventory/api/*",
            "limit": "200/minute",
            "source": "app/blueprints/inventory/routes.py",
            "notes": "Inventory management APIs.",
        },
        {
            "endpoint": "POST /batches/api/start-batch",
            "limit": "30/minute",
            "source": "app/blueprints/batches/routes.py::api_start_batch",
            "notes": "Batch creation (resource intensive).",
        },
        {
            "endpoint": "POST /billing/webhooks/stripe",
            "limit": "300/minute",
            "source": "app/blueprints/billing/routes.py::stripe_webhook",
            "notes": "Stripe webhook ingestion endpoint.",
        },
        {
            "endpoint": "GET /api/ingredients/search",
            "limit": "300/minute",
            "source": "app/blueprints/api/ingredient_routes.py::search_ingredients",
            "notes": "Ingredient search autocomplete.",
        },
        {
            "endpoint": "GET /inventory/api/search",
            "limit": "300/minute",
            "source": "app/blueprints/inventory/routes.py::api_search_inventory",
            "notes": "Inventory search autocomplete.",
        },
        {
            "endpoint": "GLOBAL DEFAULT",
            "limit": "1000/hour + 200/minute",
            "source": "app/extensions.py::limiter",
            "notes": "Applies per remote IP when no route-level override exists.",
        },
    ]

    feature_flags = {
        "FEATURE_INVENTORY_ANALYTICS": bool(current_app.config.get("FEATURE_INVENTORY_ANALYTICS", False)),
        "TOOLS_SOAP": bool(current_app.config.get("TOOLS_SOAP", True)),
        "TOOLS_CANDLES": bool(current_app.config.get("TOOLS_CANDLES", True)),
        "TOOLS_LOTIONS": bool(current_app.config.get("TOOLS_LOTIONS", True)),
        "TOOLS_HERBAL": bool(current_app.config.get("TOOLS_HERBAL", True)),
        "TOOLS_BAKING": bool(current_app.config.get("TOOLS_BAKING", True)),
    }

    logging_status = {
        "LOG_LEVEL": current_app.config.get("LOG_LEVEL", "INFO"),
        "LOG_REDACT_PII": current_app.config.get("LOG_REDACT_PII", True),
    }

    shopify_status = {
        "status": "stubbed",
        "notes": "POS/Shopify integration is stubbed. Enable later via a dedicated adapter.",
    }

    auto_backup_enabled = bool(get_setting("system.auto_backup", False))

    # Create config matrix from launch_env_sections for the table
    config_matrix = []
    for section in launch_env_sections:
        for row in section.get('rows', []):
            config_matrix.append(row)

    integration_categories = build_integration_categories(
        auto_backup_enabled=auto_backup_enabled
    )

    return render_template(
        "developer/integrations.html",
        email_provider=email_provider,
        email_configured=email_configured,
        email_keys=email_keys,
        stripe_status=stripe_status,
        tiers_count=tiers_count,
        feature_flags=feature_flags,
        logging_status=logging_status,
        shopify_status=shopify_status,
        integration_categories=integration_categories,
        env_core=env_core,
        db_info=db_info,
        cache_info=cache_info,
        host_info=host_info,
        oauth_status=oauth_status,
        whop_status=whop_status,
        rate_limiters=rate_limiters,
        launch_env_sections=launch_env_sections,
        config_matrix=config_matrix,
    )


@developer_bp.route("/integrations/test-email", methods=["POST"])
@require_developer_permission("dev.system_admin")
def integrations_test_email():
    """Send a test email to current user's email if configured."""
    try:
        if not EmailService.is_configured():
            return jsonify({"success": False, "error": "Email is not configured"}), 400
        recipient = getattr(current_user, "email", None)
        if not recipient:
            return jsonify({"success": False, "error": "Current user has no email address"}), 400
        subject = "BatchTrack Test Email"
        html_body = "<p>This is a test email from BatchTrack Integrations Checklist.</p>"
        ok = EmailService._send_email(
            recipient,
            subject,
            html_body,
            "This is a test email from BatchTrack Integrations Checklist.",
        )
        if ok:
            return jsonify({"success": True, "message": f"Test email sent to {recipient}"})
        return jsonify({"success": False, "error": "Failed to send email"}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@developer_bp.route("/integrations/test-stripe", methods=["POST"])
@require_developer_permission("dev.system_admin")
def integrations_test_stripe():
    """Test Stripe connectivity (no secrets shown)."""
    try:
        from app.services.billing_service import BillingService
        import stripe

        ok = BillingService.ensure_stripe()
        if not ok:
            return jsonify({"success": False, "error": "Stripe secret not configured"}), 400
        try:
            prices = stripe.Price.list(limit=1)
            return jsonify({"success": True, "message": f"Stripe reachable. Prices found: {len(prices.data)}"})
        except Exception as exc:
            return jsonify({"success": False, "error": f"Stripe API error: {exc}"}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@developer_bp.route("/integrations/stripe-events", methods=["GET"])
@require_developer_permission("dev.system_admin")
def integrations_stripe_events():
    """Summarize recent Stripe webhook events from the database."""
    try:
        from app.models.stripe_event import StripeEvent

        total = StripeEvent.query.count()
        last = StripeEvent.query.order_by(StripeEvent.id.desc()).first()
        payload = {"total_events": total}
        if last:
            payload.update(
                {
                    "last_event_id": last.event_id,
                    "last_event_type": last.event_type,
                    "last_status": last.status,
                    "last_processed_at": last.processed_at.isoformat() if last.processed_at else None,
                }
            )
        return jsonify({"success": True, "data": payload})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@developer_bp.route("/integrations/feature-flags/set", methods=["POST"])
@require_developer_permission("dev.system_admin")
def integrations_set_feature_flags():
    """Set feature flags via AJAX."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        toggleable_keys = DeveloperDashboardService.get_toggleable_feature_keys()
        for flag_key, enabled in data.items():
            if flag_key not in toggleable_keys:
                continue
            feature_flag = FeatureFlag.query.filter_by(key=flag_key).first()
            if feature_flag:
                feature_flag.enabled = bool(enabled)
            else:
                feature_flag = FeatureFlag(
                    key=flag_key,
                    enabled=bool(enabled),
                    description=f"Auto-created flag for {flag_key}",
                )
                db.session.add(feature_flag)

        db.session.commit()
        return jsonify({"success": True})

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


@developer_bp.route("/integrations/auto-backup", methods=["POST"])
@require_developer_permission("dev.system_admin")
def integrations_set_auto_backup():
    """Persist the auto-backup toggle (stubbed)."""
    try:
        data = request.get_json() or {}
        enabled = bool(data.get("enabled"))
        update_settings_value("system", "auto_backup", enabled)
        return jsonify({"success": True, "enabled": enabled})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@developer_bp.route("/integrations/check-webhook", methods=["GET"])
@require_developer_permission("dev.system_admin")
def integrations_check_webhook():
    """Verify webhook endpoint HTTP reachability (does not validate Stripe signature)."""
    try:
        import requests

        base = request.host_url.rstrip("/")
        url = f"{base}/billing/webhooks/stripe"
        try:
            resp = requests.get(url, timeout=5)
            status = resp.status_code
            message = "reachable (method not allowed expected)" if status == 405 else f"response {status}"
            return jsonify({"success": True, "url": url, "status": status, "message": message})
        except Exception as exc:
            return jsonify({"success": False, "url": url, "error": f"Connection error: {exc}"}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
