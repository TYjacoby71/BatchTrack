from __future__ import annotations

import os
import re

from flask import jsonify, render_template, request
from flask_login import current_user

from app.config import ENV_DIAGNOSTICS
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
                _make_item(
                    "FLASK_ENV",
                    'Runtime environment selector.',
                    required=True,
                    recommended="production",
                    note="Allowed values: development, testing, staging, production. Controls which config class loads.",
                ),
                _make_item(
                    "FLASK_SECRET_KEY",
                    "Flask session signing secret.",
                    required=True,
                    allow_config=True,
                    config_key="SECRET_KEY",
                    is_secret=True,
                    note="32+ bytes of cryptographically secure random data. Shared across all workers for cookie signing.",
                ),
                _make_item(
                    "FLASK_DEBUG",
                    "Flask debug flag. Must stay false/unset in production.",
                    required=False,
                    recommended="false / unset",
                    note="Set to 1/true only for local troubleshooting. Enabling this in staging/prod is a security risk.",
                ),
                _make_item(
                    "LOG_LEVEL",
                    "Application logging level.",
                    required=True,
                    recommended="INFO",
                    allow_config=True,
                    note="Common values: DEBUG, INFO, WARNING, ERROR. Influences both Flask logger and structured diagnostics.",
                ),
                _make_item(
                    "APP_BASE_URL",
                    "Canonical public base URL (https://app.example.com).",
                    required=True,
                    allow_config=True,
                    config_key="EXTERNAL_BASE_URL",
                    note="Must be a full absolute URL (scheme + host). Used for CSRF, absolute redirects, and template helpers.",
                ),
                _make_item(
                    "APP_HOST",
                    "Optional explicit host override for CSRF/proxy checks.",
                    required=False,
                    allow_config=True,
                    config_key="CANONICAL_HOST",
                    note="Defaults to the host portion of APP_BASE_URL. Override only when the ingress host differs from the public URL.",
                ),
            ],
        ),
        _section(
            "Database & Persistence",
            "Configure a managed Postgres instance before launch. Defaults are tuned for ~500 concurrent users unless overridden.",
            [
                _make_item("DATABASE_INTERNAL_URL", "Primary database connection string.", required=True, is_secret=True),
                _make_item("DATABASE_URL", "Fallback database connection string.", required=False, is_secret=True),
                _make_item(
                    "SQLALCHEMY_CREATE_ALL",
                    "Run db.create_all() during startup (set 1 to enable, 0 to skip).",
                    required=False,
                    recommended="0 (prod) / 1 (local seeding)",
                ),
                _make_item(
                    "SQLALCHEMY_POOL_SIZE",
                    "SQLAlchemy connection pool size (per worker process).",
                    required=False,
                    recommended="5 (baseline for ~500 concurrent users; scale with workers)",
                ),
                _make_item(
                    "SQLALCHEMY_MAX_OVERFLOW",
                    "Additional connections allowed past pool_size.",
                    required=False,
                    recommended="5",
                ),
                _make_item(
                    "SQLALCHEMY_POOL_TIMEOUT",
                    "Seconds to wait for a database connection before failing.",
                    required=False,
                    recommended="10",
                ),
                _make_item(
                    "SQLALCHEMY_POOL_RECYCLE",
                    "Seconds before recycling idle DB connections.",
                    required=False,
                    recommended="300",
                ),
                _make_item(
                    "SQLALCHEMY_POOL_USE_LIFO",
                    "Prefer most recently used connections in the pool.",
                    required=False,
                    recommended="true",
                ),
                _make_item(
                    "SQLALCHEMY_POOL_RESET_ON_RETURN",
                    "Reset behavior when returning a connection to the pool.",
                    required=False,
                    recommended="commit",
                ),
            ],
        ),
        _section(
            "Caching & Rate Limits",
            "Provision a managed Redis instance.",
            [
                _make_item("REDIS_URL", "Redis connection string.", required=True, recommended="redis://", allow_config=True),
                _make_item("SESSION_TYPE", "Server-side session backend.", required=True, recommended="redis", allow_config=True),
                _make_item(
                    "SESSION_LIFETIME_MINUTES",
                    "Session lifetime in minutes.",
                    required=False,
                    recommended="60",
                ),
                _make_item(
                    "CACHE_DEFAULT_TIMEOUT",
                    "Default cache TTL in seconds.",
                    required=False,
                    recommended="120",
                ),
                _make_item(
                    "REDIS_MAX_CONNECTIONS",
                    "Max clients allowed by your Redis plan (used to auto-budget pool per worker).",
                    required=False,
                    recommended="Set to your plan limit (example: 250)",
                ),
                _make_item(
                    "REDIS_POOL_MAX_CONNECTIONS",
                    "Shared Redis connection pool size (across cache/sessions/limiter).",
                    required=False,
                    recommended="20 (per worker, if you need a hard cap)",
                ),
                _make_item(
                    "REDIS_POOL_TIMEOUT",
                    "Seconds to wait for a Redis connection before erroring.",
                    required=False,
                    recommended="5",
                ),
                _make_item(
                    "REDIS_SOCKET_TIMEOUT",
                    "Redis socket timeout in seconds.",
                    required=False,
                    recommended="5",
                ),
                _make_item(
                    "REDIS_CONNECT_TIMEOUT",
                    "Redis connect timeout in seconds.",
                    required=False,
                    recommended="5",
                ),
            ],
        ),
        _section(
            "Security & Networking",
            "Enable proxy awareness and security headers behind your load balancer.",
            [
                _make_item(
                    "ENABLE_PROXY_FIX",
                    "Wrap the app in Werkzeug ProxyFix.",
                    required=True,
                    recommended="true",
                    note="Keeps remote_addr, scheme, and host accurate when behind a load balancer. Always true in hosted environments.",
                ),
                _make_item(
                    "TRUST_PROXY_HEADERS",
                    "Legacy proxy toggle.",
                    required=False,
                    recommended="true",
                    note="Set to true when running behind Render/NGINX/Cloudflare so Flask trusts X-Forwarded-* headers.",
                ),
                _make_item(
                    "PROXY_FIX_X_FOR",
                    "Number of X-Forwarded-For headers to trust.",
                    required=False,
                    recommended="1",
                    note="Set equal to the number of proxies in front of the app. 1 is typical for Render + CDN.",
                ),
                _make_item(
                    "FORCE_SECURITY_HEADERS",
                    "Force security headers.",
                    required=False,
                    recommended="true",
                    note="When true, middleware adds HSTS, X-Frame-Options, and related headers on every response.",
                ),
            ],
        ),
        _section(
            "Load Testing Diagnostics",
            "Optional flags for observing synthetic traffic. Legacy bypass envs (ALLOW_LOADTEST_LOGIN_BYPASS / LOADTEST_ALLOW_LOGIN_WITHOUT_CSRF) are now blocked entirely.",
            [
                _make_item(
                    "LOCUST_LOG_LOGIN_FAILURE_CONTEXT",
                    "Set to 1 to log structured auth.login failures (username, headers, cookie state).",
                    required=False,
                    recommended="unset / 0 (enable only when debugging)",
                    note="Keep disabled once the load test is green to reduce noise. Logs remain available from Locust via LOCUST_LOG_LOGIN_FAILURE_CONTEXT.",
                ),
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
        _section(
            "Load Testing Features & Inputs",
            "Environment-driven knobs consumed by loadtests/locustfile.py. All users must behave like real clients (no CSRF bypass).",
            [
                _make_item(
                    "LOCUST_USER_BASE",
                    "Username prefix for generated test accounts.",
                    required=False,
                    note="Defaults to loadtest_user. The script appends sequential numbers (e.g., loadtest_user1..N).",
                ),
                _make_item(
                    "LOCUST_USER_PASSWORD",
                    "Password shared by generated load-test users.",
                    required=False,
                    note="Defaults to loadtest123. Must match credentials created via loadtests/test_user_generator.py.",
                ),
                _make_item(
                    "LOCUST_USER_COUNT",
                    "Number of sequential users to generate.",
                    required=False,
                    note="Defaults to 10000. Set to your planned Locust concurrency (e.g., 100) so the credential pool matches the run.",
                ),
                _make_item(
                    "LOCUST_CACHE_TTL",
                    "Seconds before Locust refreshes cached IDs.",
                    required=False,
                    note="Defaults to 120 seconds. Lower for high churn data; higher to reduce bootstrap calls.",
                ),
                _make_item(
                    "LOCUST_REQUIRE_HTTPS",
                    "Require Locust host to use HTTPS (1/0).",
                    required=False,
                    note="Defaults to 1 (true). Keeps Secure cookies from being discarded if someone points Locust at http://.",
                ),
                _make_item(
                    "LOCUST_LOG_LOGIN_FAILURE_CONTEXT",
                    "Emit structured diagnostics when login fails.",
                    required=False,
                    note="Defaults to 1. Set to 0 to silence verbose JSON logs once the load test is stable.",
                ),
                _make_item(
                    "LOCUST_USER_CREDENTIALS",
                    "Optional JSON list of explicit username/password pairs.",
                    required=False,
                    note='Example: [{"username":"user1","password":"pass"}]. Overrides sequential generation when provided.',
                ),
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
