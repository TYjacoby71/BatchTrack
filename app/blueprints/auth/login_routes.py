"""Login and lightweight account access routes."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from . import auth_bp
from ...extensions import db, limiter
from ...models import GlobalItem, Organization, Role, User
from ...models.subscription_tier import SubscriptionTier
from ...services.email_service import EmailService
from ...services.oauth_service import OAuthService
from ...services.public_bot_trap_service import PublicBotTrapService
from ...services.session_service import SessionService
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


def _log_loadtest_login_context(reason: str, extra: dict | None = None) -> None:
    """Emit structured diagnostics for load-test login failures."""
    if not current_app.config.get("LOADTEST_LOG_LOGIN_FAILURE_CONTEXT"):
        return

    try:
        details = {
            "reason": reason,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "host": request.host,
            "scheme": request.scheme,
            "is_secure": request.is_secure,
            "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
            "cookies_present": bool(request.cookies),
            "session_cookie_present": "session" in request.cookies,
            "csrf_token_in_form": bool(request.form.get("csrf_token")),
            "user_agent": (request.headers.get("User-Agent") or "")[:160],
        }
        if extra:
            details.update(extra)
        current_app.logger.warning("Load test login context: %s", details)
    except Exception as exc:  # pragma: no cover - diagnostics should never fail login
        current_app.logger.warning("Failed to log load test login context: %s", exc)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("6000/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("app_routes.dashboard"))

    form = LoginForm()
    oauth_available = OAuthService.is_oauth_configured()

    # Persist "next" param for OAuth/alternate login flows
    try:
        if request.method == "GET":
            next_param = request.args.get("next")
            if next_param and isinstance(next_param, str) and next_param.startswith("/") and not next_param.startswith("//"):
                session["login_next"] = next_param
    except Exception:
        pass

    try:
        form_is_valid = request.method == "POST" and form.validate_on_submit()
    except Exception as exc:
        logger.exception("Login form validation failed: %s", exc)
        _log_loadtest_login_context("form_validation_error", {"error": str(exc)})
        flash("Unable to process login right now. Please try again.")
        return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available), 503

    if form_is_valid:
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Please provide both username and password")
            return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available)

        try:
            user = User.query.filter_by(username=username).first()
        except SQLAlchemyError as exc:
            db.session.rollback()
            logger.exception("Login query failed for %s: %s", username, exc)
            _log_loadtest_login_context("db_query_error", {"username": username})
            flash("Login temporarily unavailable. Please try again.")
            return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available), 503

        if username and username.startswith("loadtest_user"):
            logger.info(
                "Load test login attempt: %s, user_found=%s",
                username,
                bool(user),
            )
            if user:
                try:
                    password_valid = user.check_password(password or "")
                except Exception:
                    password_valid = False
                logger.info(
                    "Load test user state: is_active=%s, password_valid=%s",
                    user.is_active,
                    password_valid,
                )

        try:
            password_ok = user.check_password(password) if user else False
        except Exception as exc:
            logger.exception("Login password check failed for %s: %s", username, exc)
            _log_loadtest_login_context("password_check_error", {"username": username})
            flash("Login temporarily unavailable. Please try again.")
            return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available), 503

        if user and password_ok:
            if not user.is_active:
                if username and username.startswith("loadtest_user"):
                    logger.warning("Load test user %s is inactive", username)
                _log_loadtest_login_context("inactive_user", {"username": username})
                flash("Account is inactive. Please contact administrator.")
                return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available)

            if user.user_type != "developer" and user.email and not user.email_verified:
                try:
                    recently_sent = (
                        user.email_verification_sent_at
                        and TimezoneUtils.utc_now() - user.email_verification_sent_at < timedelta(minutes=15)
                    )
                    if not recently_sent:
                        user.email_verification_token = EmailService.generate_verification_token(user.email)
                        user.email_verification_sent_at = TimezoneUtils.utc_now()
                        db.session.commit()
                        EmailService.send_verification_email(
                            user.email,
                            user.email_verification_token,
                            user.first_name or user.username,
                        )
                except Exception as exc:
                    db.session.rollback()
                    logger.warning("Unable to queue verification email for user %s: %s", user.id, exc)

                flash(
                    "Please verify your email before logging in. We sent you a verification link.",
                    "warning",
                )
                return redirect(url_for("auth.resend_verification", email=user.email))

            login_user(user)
            SessionService.rotate_user_session(user)
            session.pop("dismissed_alerts", None)
            user.last_login = TimezoneUtils.utc_now()
            try:
                db.session.commit()
            except SQLAlchemyError as exc:
                db.session.rollback()
                logger.exception("Login commit failed for %s: %s", username, exc)
                _log_loadtest_login_context("db_commit_error", {"username": username})
                flash("Login temporarily unavailable. Please try again.")
                return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available), 503

            if user.user_type == "developer":
                return redirect(url_for("developer.dashboard"))

            try:
                next_url = session.pop("login_next", None) or request.args.get("next")
            except Exception:
                next_url = None
            if isinstance(next_url, str) and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("app_routes.dashboard"))

        _log_loadtest_login_context("invalid_credentials", {"username": username, "user_found": bool(user)})
        if username and username.startswith("loadtest_user"):
            logger.warning("Load test login failed: invalid credentials for %s", username)
        flash("Invalid username or password")
        return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available)

    return render_template("pages/auth/login.html", form=form, oauth_available=oauth_available)


def _safe_next_path(value: str | None):
    """Only allow relative, non-protocol next URLs."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    return None


def _generate_username_from_email(email: str) -> str:
    base = (email or "user").split("@")[0]
    base = re.sub(r"[^a-zA-Z0-9]+", "", base) or "user"
    candidate = base
    counter = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


@auth_bp.route("/quick-signup", methods=["GET", "POST"])
@limiter.limit("600/minute")
def quick_signup():
    """Lightweight, free-account signup used by public global item pages."""
    if current_user.is_authenticated:
        next_url = _safe_next_path(request.args.get("next")) or url_for("inventory.list_inventory")
        return redirect(next_url)

    if request.method == "POST":
        next_url = _safe_next_path(request.form.get("next")) or url_for("inventory.list_inventory")
        global_item_id = (request.form.get("global_item_id") or "").strip()

        trap_value = (request.form.get("website") or "").strip()
        if trap_value:
            trap_email = (request.form.get("email") or "").strip().lower() or None
            PublicBotTrapService.record_hit(
                request=request,
                source="quick_signup",
                reason="honeypot",
                email=trap_email,
                extra={"field": "website"},
                block=False,
            )
            if trap_email:
                blocked_user_id = PublicBotTrapService.block_email_if_user_exists(trap_email)
                PublicBotTrapService.add_block(email=trap_email, user_id=blocked_user_id)
            else:
                PublicBotTrapService.add_block(
                    ip=PublicBotTrapService.resolve_request_ip(request),
                )
            return redirect(url_for("auth.login", next=next_url))

        full_name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return render_template(
                "pages/auth/quick_signup.html",
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_name=full_name,
                prefill_email=email,
            )

        if PublicBotTrapService.is_blocked(
            ip=PublicBotTrapService.resolve_request_ip(request),
            email=email,
        ):
            PublicBotTrapService.record_hit(
                request=request,
                source="quick_signup",
                reason="blocked",
                email=email,
                extra={"flow": "quick_signup"},
                block=False,
            )
            return redirect(url_for("auth.login", next=next_url))

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template(
                "pages/auth/quick_signup.html",
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_name=full_name,
                prefill_email=email,
            )

        existing_by_email = User.query.filter_by(email=email).first()
        if existing_by_email:
            flash("An account with that email already exists. Please log in to continue.", "info")
            return redirect(url_for("auth.login", next=next_url))

        first_name = ""
        last_name = ""
        if full_name:
            parts = full_name.split()
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        try:
            tier = SubscriptionTier.find_by_identifier("free") or SubscriptionTier.find_by_identifier("exempt")

            org_name = f"{first_name or 'New'}'s Workspace"
            org = Organization(
                name=org_name,
                contact_email=email,
                is_active=True,
                signup_source="global_library",
                subscription_status="active",
                billing_status="active",
            )
            if tier:
                org.subscription_tier_id = tier.id
            db.session.add(org)
            db.session.flush()

            username = _generate_username_from_email(email)
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                organization_id=org.id,
                user_type="customer",
                is_organization_owner=True,
                is_active=True,
                email_verified=False,
                email_verification_token=EmailService.generate_verification_token(email),
                email_verification_sent_at=TimezoneUtils.utc_now(),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            org_owner_role = Role.query.filter_by(name="organization_owner", is_system_role=True).first()
            if org_owner_role:
                user.assign_role(org_owner_role)

            db.session.commit()

            try:
                EmailService.send_verification_email(
                    user.email,
                    user.email_verification_token,
                    user.first_name or user.username,
                )
            except Exception as exc:
                logger.warning("Quick-signup verification email failed for %s: %s", user.email, exc)

            flash("Account created. Please verify your email before signing in.", "success")
            return redirect(url_for("auth.login", next=next_url))
        except Exception as exc:
            db.session.rollback()
            logger.error("Quick signup failed: %s", exc, exc_info=True)
            flash("Unable to create your account right now. Please try again.", "error")
            return render_template(
                "pages/auth/quick_signup.html",
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_name=full_name,
                prefill_email=email,
            )

    next_url = _safe_next_path(request.args.get("next")) or url_for("inventory.list_inventory")
    global_item_id = (request.args.get("global_item_id") or "").strip()
    global_item_name = ""
    try:
        if global_item_id and global_item_id.isdigit():
            gi = db.session.get(GlobalItem, int(global_item_id))
            global_item_name = getattr(gi, "name", "") if gi else ""
    except Exception:
        global_item_name = ""

    return render_template(
        "pages/auth/quick_signup.html",
        next_url=next_url,
        global_item_id=global_item_id,
        global_item_name=global_item_name,
        prefill_name="",
        prefill_email="",
    )


@auth_bp.route("/logout")
def logout():
    session.pop("dev_selected_org_id", None)
    session.pop("dismissed_alerts", None)

    try:
        session.pop("tool_draft", None)
        session.pop("tool_draft_meta", None)
    except Exception:
        pass

    if current_user.is_authenticated:
        current_user.active_session_token = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    SessionService.clear_session_state()
    logout_user()
    return redirect(url_for("homepage"))


@auth_bp.route("/dev-login")
def dev_login():
    """Quick developer login for system access."""
    dev_user = User.query.filter_by(username="dev").first()
    if dev_user:
        login_user(dev_user)
        SessionService.rotate_user_session(dev_user)
        dev_user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash("Developer access granted", "success")
        return redirect(url_for("developer.dashboard"))

    flash("Developer account not found. Please contact system administrator.", "error")
    return redirect(url_for("auth.login"))
