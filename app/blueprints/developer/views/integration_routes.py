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
                _make_item("SQLALCHEMY_DISABLE_CREATE_ALL", "Disable db.create_all() safety switch.", required=False, recommended="1"),
                _make_item("SQLALCHEMY_ENABLE_CREATE_ALL", "Local dev-only override.", required=False, recommended="unset"),
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
    ]

    rate_limiters = [
        {
            "endpoint": "GET/POST /auth/login",
            "limit": "30/minute",
            "source": "app/blueprints/auth/routes.py::login",
            "notes": "Primary credential-based login form.",
        },
        {
            "endpoint": "POST /billing/webhooks/stripe",
            "limit": "60/minute",
            "source": "app/blueprints/billing/routes.py::stripe_webhook",
            "notes": "Stripe webhook ingestion endpoint.",
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
