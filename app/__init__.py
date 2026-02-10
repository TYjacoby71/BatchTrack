"""Application factory and core configuration wiring.

Synopsis:
Builds the Flask app, initializes extensions, and applies environment overrides.

Glossary:
- App factory: Function that constructs and configures the Flask app.
- Extension: Flask subsystem (db, cache, sessions, limiter) initialized per app.
"""

import logging
import os
from typing import Any

from flask import Flask, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from .authz import configure_login_manager
from .blueprints_registry import register_blueprints
from .config import ENV_DIAGNOSTICS
from .extensions import cache, csrf, db, limiter, migrate, server_session
from .logging_config import configure_logging
from .middleware import register_middleware
from .utils.cache_utils import should_bypass_cache
from .utils.redis_pool import LazyRedisClient, get_redis_pool

logger = logging.getLogger(__name__)


# --- Create app ---
# Purpose: Build and configure the Flask application instance.
def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    os.makedirs(app.instance_path, exist_ok=True)

    _load_base_config(app, config)
    _configure_sqlite_engine_options(app)
    _warn_sqlalchemy_pool_settings(app, app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))

    db.init_app(app)
    _configure_db_timeouts(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    _configure_cache(app)
    _configure_sessions(app)
    _configure_rate_limiter(app)

    configure_login_manager(app)
    register_middleware(app)
    register_blueprints(app)
    from . import models  # noqa: F401  # ensure models registered for Alembic

    from .template_context import register_template_context
    from .utils.template_filters import register_template_filters

    register_template_context(app)
    register_template_filters(app)
    _add_core_routes(app)
    configure_logging(app)
    _install_global_resilience_handlers(app)

    from .management import register_commands

    register_commands(app)
    _run_optional_create_all(app)

    return app


# --- Load base config ---
# Purpose: Apply base configuration and environment diagnostics.
def _load_base_config(app: Flask, config: dict[str, Any] | None) -> None:
    app.config.from_object("app.config.Config")
    if config:
        app.config.update(config)
    app.config["ENV_DIAGNOSTICS"] = ENV_DIAGNOSTICS
    for warning in ENV_DIAGNOSTICS.get("warnings", ()):
        logger.warning("Environment configuration warning: %s", warning)

    if app.config.get("TESTING"):
        app.config.setdefault("WTF_CSRF_ENABLED", False)

    if config and "DATABASE_URL" in config:
        app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]

    upload_dir = os.path.join(app.root_path, "static", "product_images")
    os.makedirs(upload_dir, exist_ok=True)
    app.config.setdefault("UPLOAD_FOLDER", upload_dir)
    app.config.setdefault("BATCHTRACK_ORG_ID", 1)


# --- Warn pool settings ---
# Purpose: Emit warnings for risky SQLAlchemy pool configurations.
def _warn_sqlalchemy_pool_settings(app: Flask, engine_opts: dict) -> None:
    env_name = (app.config.get("ENV") or app.config.get("FLASK_ENV") or "").lower()
    if env_name not in {"production", "staging"}:
        return

    pool_size = engine_opts.get("pool_size")
    max_overflow = engine_opts.get("max_overflow")
    pool_timeout = engine_opts.get("pool_timeout")
    pool_recycle = engine_opts.get("pool_recycle")

    if isinstance(pool_size, int) and pool_size < 10:
        logger.warning(
            "SQLALCHEMY_POOL_SIZE=%s is low for production (per worker). Expect queueing under load.",
            pool_size,
        )
    if isinstance(max_overflow, int) and max_overflow < 5:
        logger.warning(
            "SQLALCHEMY_MAX_OVERFLOW=%s is low for production (per worker).",
            max_overflow,
        )
    if isinstance(pool_timeout, (int, float)) and pool_timeout < 30:
        logger.warning(
            "SQLALCHEMY_POOL_TIMEOUT=%ss is aggressive for production; expect timeouts under load.",
            pool_timeout,
        )
    if isinstance(pool_recycle, (int, float)) and pool_recycle < 900:
        logger.warning(
            "SQLALCHEMY_POOL_RECYCLE=%ss is low; expect extra connection churn.",
            pool_recycle,
        )

    if os.environ.get("WEB_CONCURRENCY") not in (None, ""):
        logger.warning("WEB_CONCURRENCY is ignored; use GUNICORN_WORKERS instead.")

    try:
        worker_count = int(os.environ.get("GUNICORN_WORKERS") or 1)
    except (TypeError, ValueError):
        worker_count = 1
    if isinstance(pool_size, int) and worker_count > 1:
        logger.info(
            "SQLAlchemy pool sizing: workers=%s, per-worker pool_size=%s, total base=%s",
            worker_count,
            pool_size,
            worker_count * pool_size,
        )


# --- Configure cache ---
# Purpose: Initialize Flask-Caching with Redis or fallback cache.
def _configure_cache(app: Flask) -> None:
    redis_url = app.config.get("REDIS_URL")
    cache_config = {
        "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
    }

    if redis_url:
        pool = get_redis_pool(app)
        if pool is not None:
            cache_config["CACHE_TYPE"] = "RedisCache"
            cache_config["CACHE_REDIS_URL"] = redis_url
            cache_config.setdefault("CACHE_OPTIONS", {})
            cache_config["CACHE_OPTIONS"]["connection_pool"] = pool
            logger.info("Redis cache configured with shared connection pool")
        else:
            cache_config["CACHE_TYPE"] = "SimpleCache"
            logger.warning("Unable to initialize Redis cache; falling back to SimpleCache.")
    else:
        cache_config["CACHE_TYPE"] = "SimpleCache"
        logger.info("Using SimpleCache (no Redis URL configured)")

    cache.init_app(app, config=cache_config)
    if app.config.get("ENV") == "production" and cache_config["CACHE_TYPE"] != "RedisCache":
        raise RuntimeError("Redis cache not configured; SimpleCache is not permitted in production.")


# --- Configure sessions ---
# Purpose: Initialize server-side session storage.
def _configure_sessions(app: Flask) -> None:
    session_backend = None
    session_redis = None
    session_redis_url = app.config.get("REDIS_URL")

    if session_redis_url:
        try:
            import redis  # noqa: F401  # ensure package is available

            session_redis = LazyRedisClient(session_redis_url, app)
            session_backend = "redis"
        except Exception as exc:
            logger.warning("Failed to initialize Redis-backed session store (%s); falling back to filesystem.", exc)

    if session_backend == "redis" and session_redis is not None:
        app.config.setdefault("SESSION_TYPE", "redis")
        app.config.setdefault("SESSION_PERMANENT", True)
        app.config.setdefault("SESSION_USE_SIGNER", True)
        app.config["SESSION_REDIS"] = session_redis
    else:
        session_dir = os.path.join(app.instance_path, "session_files")
        os.makedirs(session_dir, exist_ok=True)
        app.config.setdefault("SESSION_FILE_DIR", session_dir)
        app.config.setdefault("SESSION_TYPE", "filesystem")
        app.config.setdefault("SESSION_PERMANENT", True)
        app.config.setdefault("SESSION_USE_SIGNER", True)
        if app.config.get("ENV") == "production":
            raise RuntimeError("Server-side sessions require Redis in production.")

    server_session.init_app(app)


# --- Configure rate limiter ---
# Purpose: Initialize Flask-Limiter and its Redis backing store.
def _configure_rate_limiter(app: Flask) -> None:
    storage_uri = app.config.get("RATELIMIT_STORAGE_URI") or "memory://"
    app.config["RATELIMIT_STORAGE_URI"] = storage_uri
    if storage_uri.startswith("redis"):
        pool = get_redis_pool(app)
        if pool is not None:
            storage_options = dict(app.config.get("RATELIMIT_STORAGE_OPTIONS") or {})
            storage_options["connection_pool"] = pool
            app.config["RATELIMIT_STORAGE_OPTIONS"] = storage_options
    limiter.init_app(app)

    if app.config.get("ENV") == "production" and storage_uri.startswith("memory://"):
        raise RuntimeError("Rate limiter storage must be Redis-backed in production.")



# --- Optional create_all ---
# Purpose: Allow optional db.create_all() for local setups.
def _run_optional_create_all(app: Flask) -> None:
    def _env_flag(key: str):
        value = os.environ.get(key)
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    def _execute_create_all(reason: str):
        logger.info("Local dev: creating tables via db.create_all() (%s)", reason)
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created/verified")
            except Exception as exc:  # pragma: no cover - dev helper
                logger.warning("Database table creation skipped: %s", exc)

    create_all_flag = _env_flag("SQLALCHEMY_CREATE_ALL")
    if create_all_flag is None:
        logger.info("db.create_all() not enabled; Alembic migrations are the source of truth")
        return
    if create_all_flag is False:
        logger.info("db.create_all() disabled via SQLALCHEMY_CREATE_ALL=0")
        return
    _execute_create_all("SQLALCHEMY_CREATE_ALL")

# --- Configure SQLite options ---
# Purpose: Remove invalid SQLAlchemy pool settings for SQLite.
def _configure_sqlite_engine_options(app):
    """Configure SQLite engine options for testing/memory databases"""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if app.config.get("TESTING") or uri.startswith("sqlite"):
        opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        # Remove pool args that SQLite memory + StaticPool don't accept
        opts.pop("pool_size", None)
        opts.pop("max_overflow", None)
        if uri == "sqlite:///:memory:":
            opts["poolclass"] = StaticPool
            opts["connect_args"] = {"check_same_thread": False}
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts


# --- Configure DB timeouts ---
# Purpose: Apply statement and lock timeouts to the DB engine.
def _configure_db_timeouts(app: Flask) -> None:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if not uri or uri.startswith("sqlite"):
        return

    timeouts = {
        "statement_timeout": app.config.get("DB_STATEMENT_TIMEOUT_MS"),
        "lock_timeout": app.config.get("DB_LOCK_TIMEOUT_MS"),
        "idle_in_transaction_session_timeout": app.config.get("DB_IDLE_TX_TIMEOUT_MS"),
    }
    settings = {}
    for key, value in timeouts.items():
        if value is None:
            continue
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            continue
        if int_value > 0:
            settings[key] = int_value

    if not settings:
        return

    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def _set_session_timeouts(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            try:
                for key, value in settings.items():
                    cursor.execute(f"SET {key} = {value}")
            finally:
                cursor.close()

# --- Install resilience handlers ---
# Purpose: Add global error handlers for known failure modes.
def _install_global_resilience_handlers(app):
    """Install global DB rollback and friendly maintenance handler."""
    from sqlalchemy.exc import OperationalError, DBAPIError, SQLAlchemyError
    from .extensions import db
    from flask import render_template, request
    from flask_wtf.csrf import CSRFError

    @app.teardown_request
    def _rollback_on_error(exc):
        try:
            if exc is not None:
                db.session.rollback()
        except Exception:
            pass
        finally:
            try:
                db.session.remove()
            except Exception:
                pass

    @app.errorhandler(OperationalError)
    @app.errorhandler(DBAPIError)
    def _db_error_handler(e):
        try:
            db.session.rollback()
        except Exception:
            pass
        # Return lightweight 503 page; avoid cascading errors if template missing
        try:
            return render_template("errors/maintenance.html"), 503
        except Exception:
            return ("Service temporarily unavailable. Please try again shortly.", 503)

    @app.errorhandler(CSRFError)
    def _csrf_error_handler(err: CSRFError):
        """Emit structured diagnostics so load tests can see *why* CSRF failed."""
        details = {
            "path": request.path,
            "endpoint": request.endpoint,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string if request.user_agent else None,
            "reason": err.description,
        }
        app.logger.warning("CSRF validation failed: %s", details)
        rendered = None
        try:
            rendered = render_template("errors/csrf.html", reason=err.description, details=details)
        except Exception:
            pass
        if rendered is not None:
            return rendered, 400
        return "CSRF validation failed. Please refresh and try again.", 400

# --- Add core routes ---
# Purpose: Register basic app-wide routes like health checks.
def _add_core_routes(app):
    """Add core application routes"""
    def _render_public_homepage_response():
        """
        Serve the marketing homepage with Redis caching so anonymous traffic (and load tests)
        avoid re-rendering the full template on every hit.
        """
        cache_key = current_app.config.get("PUBLIC_HOMEPAGE_CACHE_KEY", "public:homepage:v1")
        try:
            from app.utils.settings import is_feature_enabled

            global_library_enabled = is_feature_enabled("FEATURE_GLOBAL_ITEM_LIBRARY")
            cache_key = f"{cache_key}:global_library:{'on' if global_library_enabled else 'off'}"
        except Exception:
            pass
        try:
            cache_ttl = int(current_app.config.get("PUBLIC_HOMEPAGE_CACHE_TTL", 600))
        except (TypeError, ValueError):
            cache_ttl = 600
        cache_ttl = max(0, cache_ttl)

        if cache_ttl and not should_bypass_cache():
            cached_page = cache.get(cache_key)
            if cached_page is not None:
                return cached_page

        rendered = render_template("homepage.html")
        if cache_ttl:
            try:
                cache.set(cache_key, rendered, timeout=cache_ttl)
            except Exception:
                # Homepage rendering should never fail because cache is unavailable.
                pass
        return rendered

    def _normalize_feature_label(value: str | None) -> str:
        cleaned = " ".join(str(value or "").replace(".", " ").replace("_", " ").split())
        return cleaned.strip().lower()

    def _display_feature_label(value: str | None) -> str:
        normalized = _normalize_feature_label(value)
        if not normalized:
            return ""
        return " ".join(token.capitalize() for token in normalized.split())

    def _build_public_pricing_context() -> dict[str, Any]:
        from app.services.lifetime_pricing_service import LifetimePricingService
        from app.services.signup_checkout_service import SignupCheckoutService

        signup_context = SignupCheckoutService.build_request_context(request=request, oauth_user_info=None)
        available_tiers = signup_context.available_tiers
        lifetime_offers = signup_context.lifetime_offers
        offers_by_key = {
            str(offer.get("key", "")).strip().lower(): offer for offer in lifetime_offers if offer
        }

        ordered_keys = ("hobbyist", "enthusiast", "fanatic")
        pricing_tiers: list[dict[str, Any]] = []

        for tier_key in ordered_keys:
            offer = offers_by_key.get(tier_key, {})
            tier_id = str(offer.get("tier_id") or "")
            tier_data = available_tiers.get(tier_id) if tier_id else None

            if not tier_data:
                for candidate_tier_id, candidate_tier_data in available_tiers.items():
                    candidate_name = str(candidate_tier_data.get("name", "")).strip().lower()
                    if candidate_name == tier_key:
                        tier_data = candidate_tier_data
                        tier_id = str(candidate_tier_id)
                        break

            raw_feature_names = (tier_data or {}).get("all_features") or []
            all_feature_labels: list[str] = []
            all_feature_set: set[str] = set()
            for raw_feature_name in raw_feature_names:
                feature_label = LifetimePricingService.format_feature_label(raw_feature_name)
                normalized_feature = _normalize_feature_label(feature_label)
                if not normalized_feature or normalized_feature in all_feature_set:
                    continue
                all_feature_set.add(normalized_feature)
                all_feature_labels.append(feature_label)

            highlight_features: list[str] = []
            highlight_seen: set[str] = set()
            for feature in (tier_data or {}).get("features", []):
                feature_label = _display_feature_label(feature)
                normalized_feature = _normalize_feature_label(feature_label)
                if not normalized_feature or normalized_feature in highlight_seen:
                    continue
                highlight_seen.add(normalized_feature)
                highlight_features.append(feature_label)

            if not highlight_features:
                highlight_features = all_feature_labels[:6]

            has_yearly_price = bool((tier_data or {}).get("yearly_price_display"))
            has_lifetime_remaining = bool(offer.get("has_remaining") and tier_id)

            monthly_url = (
                url_for(
                    "auth.signup",
                    tier=tier_id,
                    billing_mode="standard",
                    billing_cycle="monthly",
                    source=f"pricing_{tier_key}_monthly",
                )
                if tier_id
                else None
            )
            yearly_url = (
                url_for(
                    "auth.signup",
                    tier=tier_id,
                    billing_mode="standard",
                    billing_cycle="yearly",
                    source=f"pricing_{tier_key}_yearly",
                )
                if tier_id and has_yearly_price
                else None
            )
            lifetime_url = (
                url_for(
                    "auth.signup",
                    billing_mode="lifetime",
                    lifetime_tier=offer.get("key"),
                    tier=tier_id,
                    promo=offer.get("coupon_code"),
                    source=f"pricing_{tier_key}_lifetime",
                )
                if has_lifetime_remaining
                else None
            )

            pricing_tiers.append(
                {
                    "key": tier_key,
                    "name": str(offer.get("name") or tier_key.title()),
                    "tagline": str(offer.get("tagline") or "Built for makers"),
                    "future_scope": str(offer.get("future_scope") or ""),
                    "tier_id": tier_id,
                    "monthly_price_display": (tier_data or {}).get("monthly_price_display"),
                    "yearly_price_display": (tier_data or {}).get("yearly_price_display"),
                    "feature_highlights": highlight_features,
                    "all_feature_labels": all_feature_labels,
                    "all_feature_set": all_feature_set,
                    "feature_total": int((tier_data or {}).get("feature_total") or len(all_feature_labels)),
                    "lifetime_offer": offer,
                    "lifetime_has_remaining": has_lifetime_remaining,
                    "signup_monthly_url": monthly_url,
                    "signup_yearly_url": yearly_url,
                    "signup_lifetime_url": lifetime_url,
                }
            )

        comparison_labels: list[str] = []
        comparison_seen: set[str] = set()
        for tier in pricing_tiers:
            for feature_label in tier.get("feature_highlights", []):
                normalized_label = _normalize_feature_label(feature_label)
                if not normalized_label or normalized_label in comparison_seen:
                    continue
                comparison_seen.add(normalized_label)
                comparison_labels.append(_display_feature_label(feature_label))

            for feature_label in tier.get("all_feature_labels", []):
                normalized_label = _normalize_feature_label(feature_label)
                if not normalized_label or normalized_label in comparison_seen:
                    continue
                comparison_seen.add(normalized_label)
                comparison_labels.append(_display_feature_label(feature_label))

        if not comparison_labels:
            comparison_labels = [
                "Inventory Tracking",
                "Recipe Management",
                "Batch Production Workflow",
                "Real-time Stock Alerts",
                "FIFO Lot Tracking",
                "Organization Collaboration",
                "Advanced Analytics",
                "Priority Support",
            ]

        comparison_rows: list[dict[str, Any]] = []
        for feature_label in comparison_labels[:18]:
            normalized_label = _normalize_feature_label(feature_label)
            row: dict[str, Any] = {"label": feature_label}
            for tier in pricing_tiers:
                row[tier["key"]] = normalized_label in tier.get("all_feature_set", set())
            comparison_rows.append(row)

        lifetime_has_capacity = any(tier.get("lifetime_has_remaining") for tier in pricing_tiers)

        return {
            "pricing_tiers": pricing_tiers,
            "comparison_rows": comparison_rows,
            "lifetime_has_capacity": lifetime_has_capacity,
        }

    @app.route("/")
    def index():
        """Main landing page with proper routing logic"""
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))  # Developers go to developer dashboard
            else:
                return redirect(url_for('app_routes.dashboard'))  # Regular users go to user dashboard
        else:
            return _render_public_homepage_response()  # Serve cached public homepage for unauthenticated users

    @app.route("/homepage")
    def homepage():
        """Public homepage - accessible to all users"""
        return _render_public_homepage_response()

    @app.route("/public")
    def public_page():
        """Alternative public page"""
        return _render_public_homepage_response()

    @app.route("/pricing")
    def pricing():
        """Public pricing and plan comparison page."""
        pricing_context = _build_public_pricing_context()
        return render_template(
            "pages/public/pricing.html",
            show_public_header=True,
            page_title="BatchTrack.com | Pricing for Small-Batch Makers",
            page_description=(
                "Compare Hobbyist, Enthusiast, and Fanatic plans with monthly, yearly, "
                "and limited lifetime launch seats."
            ),
            canonical_url=url_for("pricing", _external=True),
            **pricing_context,
        )

# --- Setup logging ---
# Purpose: Configure log levels and app log formatters.
def _setup_logging(app):
    """Retained for backward compatibility; logging is configured via logging_config."""
    pass

