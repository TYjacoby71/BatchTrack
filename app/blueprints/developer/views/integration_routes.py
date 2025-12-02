from __future__ import annotations

import os
import re

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.services.email_service import EmailService

from ..routes import developer_bp


@developer_bp.route("/integrations")
@login_required
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
        "FLASK_ENV": os.environ.get("FLASK_ENV", "development"),
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
    elif os.environ.get("DATABASE_INTERNAL_URL"):
        source = "DATABASE_INTERNAL_URL"
    elif os.environ.get("DATABASE_URL"):
        source = "DATABASE_URL"
    else:
        source = "config"
    db_info = {
        "uri": _mask_url(uri),
        "backend": backend,
        "source": source,
        "DATABASE_INTERNAL_URL_present": bool(os.environ.get("DATABASE_INTERNAL_URL")),
        "DATABASE_URL_present": bool(os.environ.get("DATABASE_URL")),
    }

    cache_info = {
        "RATELIMIT_STORAGE_URL": current_app.config.get("RATELIMIT_STORAGE_URL", "memory://"),
        "REDIS_URL_present": bool(os.environ.get("REDIS_URL")),
    }

    oauth_status = {
        "GOOGLE_OAUTH_CLIENT_ID_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")),
        "GOOGLE_OAUTH_CLIENT_SECRET_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")),
    }
    whop_status = {
        "WHOP_API_KEY_present": bool(current_app.config.get("WHOP_API_KEY")),
        "WHOP_APP_ID_present": bool(current_app.config.get("WHOP_APP_ID")),
    }

    def _env_status(key, *, allow_config=False, config_key=None):
        raw = os.environ.get(key)
        if raw not in (None, ""):
            return True, "env"
        if allow_config:
            cfg_val = current_app.config.get(config_key or key)
            if cfg_val not in (None, ""):
                return True, "config"
        return False, "missing"

    def _make_item(
        key,
        description,
        *,
        required=True,
        recommended=None,
        allow_config=False,
        config_key=None,
        is_secret=False,
        note=None,
    ):
        present, source = _env_status(key, allow_config=allow_config, config_key=config_key)
        return {
            "key": key,
            "description": description,
            "present": present,
            "source": source,
            "required": required,
            "recommended": recommended,
            "is_secret": is_secret,
            "note": note,
            "allow_config": allow_config,
        }

    def _section(title, note, items):
        rows = []
        for item in items:
            rows.append(
                {
                    "category": title,
                    "key": item["key"],
                    "present": item["present"],
                    "required": item["required"],
                    "recommended": item.get("recommended"),
                    "description": item["description"],
                    "note": item.get("note"),
                    "is_secret": item.get("is_secret", False),
                    "source": item.get("source", "missing"),
                }
            )
        return {"title": title, "note": note, "rows": rows}

    launch_env_sections = [
        _section(
            "Core Runtime & Platform",
            "Set these to lock the app into production mode before launch.",
            [
                _make_item("FLASK_ENV", 'Runtime environment. Use "production" for live deployments.', required=True, recommended="production", allow_config=True, config_key="ENV"),
                _make_item("FLASK_SECRET_KEY", "Flask session signing secret.", required=True, allow_config=True, config_key="SECRET_KEY", is_secret=True),
                _make_item("FLASK_DEBUG", "Flask debug flag. Must stay false/unset in production.", required=False, recommended="false / unset"),
                _make_item("LOG_LEVEL", "Application logging level.", required=True, recommended="INFO", allow_config=True),
            ],
        ),
        _section(
            "Database & Persistence",
            "Configure a managed Postgres instance before launch.",
            [
                _make_item("DATABASE_INTERNAL_URL", "Primary database connection string.", required=True, is_secret=True),
                _make_item("DATABASE_URL", "Fallback database connection string.", required=False, is_secret=True),
                _make_item(
                    "SQLALCHEMY_CREATE_ALL",
                    "Run db.create_all() during startup (set 1 to enable, 0 to skip).",
                    required=False,
                    recommended="0 (prod) / 1 (local seeding)",
                    note="Legacy SQLALCHEMY_DISABLE/ENABLE_CREATE_ALL env vars are still honored.",
                ),
            ],
        ),
        _section(
            "Caching & Rate Limits",
            "Provision a managed Redis instance.",
            [
                _make_item("REDIS_URL", "Redis connection string.", required=True, recommended="redis://", allow_config=True),
                _make_item("SESSION_TYPE", "Server-side session backend.", required=True, recommended="redis", allow_config=True),
            ],
        ),
        _section(
            "Security & Networking",
            "Enable proxy awareness and security headers behind your load balancer.",
            [
                _make_item("ENABLE_PROXY_FIX", "Wrap the app in Werkzeug ProxyFix.", required=True, recommended="true"),
                _make_item("TRUST_PROXY_HEADERS", "Legacy proxy toggle.", required=False, recommended="true"),
                _make_item("PROXY_FIX_X_FOR", "Number of X-Forwarded-For headers to trust.", required=False, recommended="1"),
                _make_item("FORCE_SECURITY_HEADERS", "Force security headers.", required=False, recommended="true"),
            ],
        ),
        _section(
            "Email & Notifications",
            "Configure exactly one provider for transactional email.",
            [
                _make_item("EMAIL_PROVIDER", "Email provider selector.", required=True, allow_config=True),
                _make_item("MAIL_SERVER", "SMTP server hostname.", required=False),
                _make_item("MAIL_USERNAME", "SMTP username.", required=False, is_secret=True),
                _make_item("SENDGRID_API_KEY", "SendGrid API key.", required=False, is_secret=True),
            ],
        ),
        _section(
            "AI Studio & BatchBot",
            "These keys and knobs control Batchley (paid bot), the public help bot, and refill economics.",
            [
                _make_item("FEATURE_BATCHBOT", "Master toggle for exposing Batchley endpoints.", required=False, recommended="true", allow_config=True, note="Set to false to completely disable the AI copilot and its routes."),
                _make_item("GOOGLE_AI_API_KEY", "Gemini API key used by Batchley + public bot.", required=True, is_secret=True, note="Create in Google AI Studio → API Key. Rotate if compromised."),
                _make_item("GOOGLE_AI_DEFAULT_MODEL", "Fallback Gemini model when per-bot overrides are unset.", required=False, recommended="gemini-1.5-flash"),
                _make_item("GOOGLE_AI_BATCHBOT_MODEL", "Model used by the paid Batchley bot.", required=False, recommended="gemini-1.5-pro"),
                _make_item("GOOGLE_AI_PUBLICBOT_MODEL", "Model used by the public help bot.", required=False, recommended="gemini-1.5-flash"),
                _make_item("GOOGLE_AI_ENABLE_SEARCH", "Enable Google Search grounding for Batchley.", required=False, recommended="true"),
                _make_item("GOOGLE_AI_ENABLE_FILE_SEARCH", "Enable File Search (uploaded docs) for prompts.", required=False, recommended="true"),
                _make_item("GOOGLE_AI_SEARCH_TOOL", "Search tool identifier sent to Gemini.", required=False, recommended="google_search"),
                _make_item("BATCHBOT_REQUEST_TIMEOUT_SECONDS", "Gemini request timeout. Increase for long-running jobs.", required=False, recommended="45"),
                _make_item("BATCHBOT_DEFAULT_MAX_REQUESTS", "Base allowance per org per window. Use -1 for unlimited tiers.", required=True, note="Tier-specific overrides live on Subscription Tiers → Max BatchBot Requests."),
                _make_item("BATCHBOT_REQUEST_WINDOW_DAYS", "Length of the usage window (credits reset after this).", required=True, recommended="30"),
                _make_item("BATCHBOT_CHAT_MAX_MESSAGES", "Max chat-only prompts per window.", required=False, recommended="60", note="≈15 conversations. Raise for higher tiers or set -1 for unlimited."),
                _make_item("BATCHBOT_COST_PER_MILLION_INPUT", "Reference compute cost for inbound tokens (USD).", required=False, recommended="0.35"),
                _make_item("BATCHBOT_COST_PER_MILLION_OUTPUT", "Reference compute cost for outbound tokens (USD).", required=False, recommended="0.53"),
                _make_item("BATCHBOT_SIGNUP_BONUS_REQUESTS", "Promo credits granted to new orgs.", required=False, recommended="20"),
                _make_item("BATCHBOT_REFILL_LOOKUP_KEY", "Stripe price lookup key for Batchley refill add-on.", required=False, recommended="batchbot_refill_100", note="Must match the Stripe price ID tied to the refill add-on."),
            ],
        ),
        _section(
            "OAuth & Marketplace",
            "Optional integrations for single sign-on and marketplace licensing.",
            [
                _make_item("GOOGLE_OAUTH_CLIENT_ID", "Google OAuth 2.0 client ID for login.", required=False, is_secret=True),
                _make_item("GOOGLE_OAUTH_CLIENT_SECRET", "Google OAuth 2.0 client secret.", required=False, is_secret=True),
                _make_item("WHOP_API_KEY", "Whop API key (if using Whop).", required=False, is_secret=True),
                _make_item("WHOP_APP_ID", "Whop app ID (if using Whop).", required=False, is_secret=True),
            ],
        ),
        _section(
            "Maintenance & Utilities",
            "Rarely used toggles for seeding or one-off maintenance scripts.",
            [
                _make_item("SEED_PRESETS", "Enable preset data seeding during migrations.", required=False, recommended="unset"),
            ],
        ),
    ]

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
        env_core=env_core,
        db_info=db_info,
        cache_info=cache_info,
        oauth_status=oauth_status,
        whop_status=whop_status,
        rate_limiters=rate_limiters,
        config_sections=launch_env_sections,
    )


@developer_bp.route("/integrations/test-email", methods=["POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
def integrations_set_feature_flags():
    """Set feature flags via AJAX."""
    from app.extensions import db
    from app.models.feature_flag import FeatureFlag

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        for flag_key, enabled in data.items():
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


@developer_bp.route("/integrations/check-webhook", methods=["GET"])
@login_required
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
