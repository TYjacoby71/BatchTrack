"""Login and lightweight account access routes.

Synopsis:
Handles username/password login, quick signup, and logout flows.
Applies optional email-verification prompting or enforcement based on env mode.

Glossary:
- Prompt mode: Unverified users can log in but are nudged to verify email.
- Required mode: Unverified users are blocked from login until verified.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from ...extensions import limiter
from ...models import User
from ...services.analytics_tracking_service import AnalyticsTrackingService
from ...services.auth_login_route_service import AuthLoginRouteService
from ...services.billing.orchestrators.auth_billing_orchestrator import (
    AuthBillingOrchestrator,
)
from ...services.billing_access_policy_service import BillingAccessAction
from ...services.email_service import EmailService
from ...services.login_lockout_service import LoginLockoutService
from ...services.oauth_service import OAuthService
from ...services.public_bot_trap_service import PublicBotTrapService
from ...services.session_service import SessionService
from ...utils.analytics_timing import seconds_since_first_landing
from ...utils.timezone_utils import TimezoneUtils
from . import auth_bp

logger = logging.getLogger(__name__)


# --- Loadtest login diagnostics ---
# Purpose: Emit safe context for debugging load-test auth failures.
# Inputs: Failure reason string plus optional structured context dictionary.
# Outputs: Conditional warning log entry when loadtest diagnostics are enabled.
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


# --- Login form ---
# Purpose: Validate credential form input for the login route.
# Inputs: Username/email and password field submissions.
# Outputs: Flask-WTF form validation state for login processing.
class LoginForm(FlaskForm):
    username = StringField("Email or Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


# --- Send verification if needed ---
# Purpose: Issue and email a fresh verification token with a resend cooldown.
# Inputs: User model for the account currently attempting to log in.
# Outputs: Boolean indicating whether a verification email was successfully sent.
def _send_verification_if_needed(user: User, *, force: bool = False) -> bool:
    """Issue and send verification token when prompt/required mode is active."""
    if not user.email or user.email_verified:
        return False
    if not EmailService.should_issue_verification_tokens():
        return False

    try:
        sent_at = TimezoneUtils.ensure_timezone_aware(user.email_verification_sent_at)
        recently_sent = sent_at and TimezoneUtils.utc_now() - sent_at < timedelta(
            minutes=15
        )
        if not force and recently_sent and user.email_verification_token:
            return False

        AuthLoginRouteService.issue_email_verification_token(user)

        sent = EmailService.send_verification_email(
            user.email,
            user.email_verification_token,
            user.first_name or user.username,
        )
        if not sent:
            # Do not enforce resend cooldown when delivery failed.
            user.email_verification_token = None
            user.email_verification_sent_at = None
            try:
                AuthLoginRouteService.commit_session()
            except Exception as clear_exc:
                logger.warning(
                    "Suppressed exception fallback at app/blueprints/auth/login_routes.py:128",
                    exc_info=True,
                )
                AuthLoginRouteService.rollback_session()
                logger.warning(
                    "Failed to clear verification token after send failure for user %s: %s",
                    user.id,
                    clear_exc,
                )
        return sent
    except Exception as exc:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/login_routes.py:136",
            exc_info=True,
        )
        AuthLoginRouteService.rollback_session()
        logger.warning(
            "Unable to queue verification email for user %s: %s", user.id, exc
        )
        return False


# --- Evaluate age-based verification lock ---
# Purpose: Enforce verification login lock for older unverified customer accounts.
# Inputs: User model with created_at timestamp and verification state.
# Outputs: Tuple[should_lock, account_age_days, grace_window_days].
def _age_based_verification_lock(user: User) -> tuple[bool, int, int]:
    grace_days_raw = current_app.config.get("AUTH_EMAIL_FORCE_REQUIRED_AFTER_DAYS", 10)
    try:
        grace_days = max(0, int(grace_days_raw))
    except (TypeError, ValueError):
        grace_days = 10

    if grace_days <= 0:
        return False, 0, grace_days

    created_at = TimezoneUtils.ensure_timezone_aware(getattr(user, "created_at", None))
    if not created_at:
        return False, 0, grace_days

    account_age_days = max(0, (TimezoneUtils.utc_now() - created_at).days)
    return account_age_days >= grace_days, account_age_days, grace_days


# --- Login route ---
# Purpose: Authenticate users and apply env-driven unverified email behavior.
# Inputs: Login form credentials and current auth-email policy configuration.
# Outputs: Redirect/HTML response with session state updates and auth-email guidance.
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("6000/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("app_routes.dashboard"))

    form = LoginForm()
    oauth_available = OAuthService.is_oauth_configured()
    show_forgot_password = EmailService.password_reset_enabled()
    show_resend_verification = EmailService.should_issue_verification_tokens()
    login_page_context = {
        "page_title": "BatchTrack Login | Production & Inventory",
        "page_description": "Sign in to BatchTrack to manage production planning, inventory, recipes, and batches.",
        "canonical_url": url_for("auth.login", _external=True),
        "show_public_header": True,
        "lightweight_public_shell": True,
        "load_analytics": False,
        "load_fontawesome": False,
        "load_feedback_widget": False,
        "public_header_signup_source": "login_start_free_trial",
    }

    def _render_login_page(status_code: int | None = None):
        rendered = render_template(
            "pages/auth/login.html",
            form=form,
            oauth_available=oauth_available,
            show_forgot_password=show_forgot_password,
            show_resend_verification=show_resend_verification,
            **login_page_context,
        )
        if status_code is not None:
            return rendered, status_code
        return rendered

    # Persist "next" param for OAuth/alternate login flows
    try:
        if request.method == "GET":
            next_param = request.args.get("next")
            if (
                next_param
                and isinstance(next_param, str)
                and next_param.startswith("/")
                and not next_param.startswith("//")
            ):
                session["login_next"] = next_param
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/login_routes.py:216",
            exc_info=True,
        )
        pass

    try:
        form_is_valid = request.method == "POST" and form.validate_on_submit()
    except Exception as exc:
        logger.exception("Login form validation failed: %s", exc)
        _log_loadtest_login_context("form_validation_error", {"error": str(exc)})
        flash("Unable to process login right now. Please try again.", "error")
        return _render_login_page(503)

    if form_is_valid:
        login_identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password")

        if not login_identifier or not password:
            flash("Please provide both email/username and password.", "error")
            return _render_login_page()

        try:
            normalized_identifier = login_identifier.lower()
            user = AuthLoginRouteService.find_user_by_login_identifier(
                normalized_identifier=normalized_identifier
            )
        except SQLAlchemyError as exc:
            AuthLoginRouteService.rollback_session()
            logger.exception("Login query failed for %s: %s", login_identifier, exc)
            _log_loadtest_login_context(
                "db_query_error", {"identifier": login_identifier}
            )
            flash("Login temporarily unavailable. Please try again.", "error")
            return _render_login_page(503)

        if login_identifier and login_identifier.startswith("[REDACTED]"):
            logger.info(
                "Load test login attempt: %s, user_found=%s",
                login_identifier,
                bool(user),
            )
            if user:
                try:
                    password_valid = user.check_password(password or "")
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/blueprints/auth/login_routes.py:265",
                        exc_info=True,
                    )
                    password_valid = False
                logger.info(
                    "Load test user state: is_active=%s, password_valid=%s",
                    user.is_active,
                    password_valid,
                )

        try:
            password_ok = user.check_password(password) if user else False
        except Exception as exc:
            logger.exception(
                "Login password check failed for %s: %s", login_identifier, exc
            )
            _log_loadtest_login_context(
                "password_check_error", {"identifier": login_identifier}
            )
            flash("Login temporarily unavailable. Please try again.", "error")
            return _render_login_page(503)

        lockout_state = LoginLockoutService.is_locked(
            user_id=getattr(user, "id", None),
            identifier=normalized_identifier,
        )
        if lockout_state.locked:
            flash(
                "Too many failed login attempts. Please reset your password to unlock your account.",
                "error",
            )
            return redirect(url_for("auth.forgot_password"))

        if user and password_ok:
            if not user.is_active:
                if login_identifier and login_identifier.startswith("[REDACTED]"):
                    logger.warning("Load test user %s is inactive", login_identifier)
                _log_loadtest_login_context(
                    "inactive_user", {"identifier": login_identifier}
                )
                flash("Account is inactive. Please contact administrator.", "error")
                return _render_login_page()

            if user.user_type != "developer":
                organization = getattr(user, "organization", None)
                billing_decision = AuthBillingOrchestrator.evaluate_organization_access(
                    organization
                )
                if billing_decision.action == BillingAccessAction.HARD_LOCK:
                    _log_loadtest_login_context(
                        "inactive_organization",
                        {
                            "identifier": login_identifier,
                            "organization_present": organization is not None,
                            "organization_billing_status": (
                                (
                                    getattr(organization, "billing_status", "inactive")
                                    or "inactive"
                                ).lower()
                                if organization is not None
                                else "inactive"
                            ),
                            "billing_reason": billing_decision.reason,
                        },
                    )
                    flash(billing_decision.message, "error")
                    return _render_login_page()

            if user.user_type != "developer" and user.email and not user.email_verified:
                force_age_prompt, account_age_days, grace_days = (
                    _age_based_verification_lock(user)
                    if EmailService.should_issue_verification_tokens()
                    else (False, 0, 0)
                )
                sent = _send_verification_if_needed(user, force=force_age_prompt)
                if EmailService.should_require_verified_email_on_login():
                    if sent:
                        flash(
                            "Please verify your email before logging in. We sent you a verification link.",
                            "warning",
                        )
                    else:
                        flash(
                            "Please verify your email before logging in. We could not send a verification email right now; use resend verification and check email provider settings.",
                            "warning",
                        )
                    return redirect(
                        url_for("auth.resend_verification", email=user.email)
                    )
                if EmailService.should_issue_verification_tokens():
                    if force_age_prompt:
                        session["verification_required_modal"] = {
                            "sent": bool(sent),
                            "age_days": int(account_age_days),
                            "grace_days": int(grace_days),
                            "email": user.email,
                        }
                        if sent:
                            flash(
                                f"We sent a new verification email because this account is older than {grace_days} days and still unverified. Please check your inbox and verify.",
                                "warning",
                            )
                        else:
                            flash(
                                "Your account needs email verification. We could not send a verification email automatically right now; use resend verification and check email provider settings.",
                                "warning",
                            )
                    elif sent:
                        flash(
                            "Please verify your email while you finish account setup. A verification link was sent.",
                            "info",
                        )
                    else:
                        flash(
                            "Please verify your email while you finish account setup. We could not send a verification email right now; use resend verification and check email provider settings.",
                            "info",
                        )

            login_user(user)
            LoginLockoutService.clear_failures(
                user_id=user.id,
                identifiers=[login_identifier, user.username or "", user.email or ""],
            )
            SessionService.rotate_user_session(user)
            session.pop("dismissed_alerts", None)
            previous_last_login = TimezoneUtils.ensure_timezone_aware(
                getattr(user, "last_login", None)
            )
            user.last_login = TimezoneUtils.utc_now()
            try:
                AuthLoginRouteService.commit_session()
            except SQLAlchemyError as exc:
                AuthLoginRouteService.rollback_session()
                logger.exception(
                    "Login commit failed for %s: %s", login_identifier, exc
                )
                _log_loadtest_login_context(
                    "db_commit_error", {"identifier": login_identifier}
                )
                flash("Login temporarily unavailable. Please try again.", "error")
                return _render_login_page(503)

            AnalyticsTrackingService.track_user_login_succeeded(
                organization_id=getattr(user, "organization_id", None),
                user_id=user.id,
                is_first_login=previous_last_login is None,
                login_method="password",
                destination_hint=(
                    "developer_dashboard"
                    if user.user_type == "developer"
                    else "app_dashboard"
                ),
                seconds_since_first_landing=seconds_since_first_landing(request),
            )

            if user.user_type == "developer":
                return redirect(url_for("developer.dashboard"))

            try:
                next_url = session.pop("login_next", None) or request.args.get("next")
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/blueprints/auth/login_routes.py:408",
                    exc_info=True,
                )
                next_url = None
            if (
                isinstance(next_url, str)
                and next_url.startswith("/")
                and not next_url.startswith("//")
            ):
                return redirect(next_url)
            return redirect(url_for("app_routes.dashboard"))

        _log_loadtest_login_context(
            "invalid_credentials",
            {"identifier": login_identifier, "user_found": bool(user)},
        )
        post_failure_state = LoginLockoutService.record_failure(
            user_id=getattr(user, "id", None),
            identifier=normalized_identifier,
        )
        if login_identifier and login_identifier.startswith("[REDACTED]"):
            logger.warning(
                "Load test login failed: invalid credentials for %s", login_identifier
            )
        if post_failure_state.locked:
            flash(
                "Too many failed login attempts. Please reset your password to unlock your account.",
                "error",
            )
            return redirect(url_for("auth.forgot_password"))
        else:
            flash("Invalid email/username or password.", "error")
        return _render_login_page()

    return _render_login_page()


# --- Sanitize next path ---
# Purpose: Prevent open redirects by allowing only safe relative paths.
# Inputs: Optional next URL/path candidate.
# Outputs: Safe relative path string or None when invalid/unsafe.
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


def _normalize_signup_source(
    value: str | None, *, fallback: str = "quick_signup"
) -> str:
    """Normalize quick-signup source tags for analytics-safe tracking."""
    raw = (value or "").strip().lower()
    if not raw:
        return fallback
    normalized = re.sub(r"[^a-z0-9._-]+", "_", raw).strip("._-")
    return normalized or fallback


# --- Generate username from email ---
# Purpose: Build a unique username candidate for quick-signup accounts.
# Inputs: Raw email address string.
# Outputs: Unique username string derived from local-part and numeric suffixes.
def _generate_username_from_email(email: str) -> str:
    base = (email or "user").split("@")[0]
    base = re.sub(r"[^a-zA-Z0-9]+", "", base) or "user"
    candidate = base
    counter = 1
    while User.username_exists(candidate):
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


# --- Quick signup route ---
# Purpose: Create a lightweight account from public pages and enter onboarding.
# Inputs: Public signup form payload plus optional return path/global item context.
# Outputs: Rendered form, validation feedback, or authenticated redirect after creation.
@auth_bp.route("/quick-signup", methods=["GET", "POST"])
@limiter.limit("600/minute")
def quick_signup():
    """Lightweight, free-account signup used by public global item pages."""
    if current_user.is_authenticated:
        next_url = _safe_next_path(request.args.get("next")) or url_for(
            "inventory.list_inventory"
        )
        return redirect(next_url)

    quick_signup_page_context = {
        "page_title": "Create a Free BatchTrack Account",
        "page_description": "Create your free BatchTrack account to save inventory items, recipes, and production workflows.",
        "canonical_url": url_for("auth.quick_signup", _external=True),
        "show_public_header": True,
        "lightweight_public_shell": True,
        "load_analytics": False,
        "load_fontawesome": False,
        "load_feedback_widget": False,
    }

    def _resolve_free_tools_tier():
        return AuthLoginRouteService.resolve_free_tools_tier()

    def _render_quick_signup_form(
        *,
        next_url: str,
        global_item_id: str,
        global_item_name: str,
        prefill_first_name: str,
        prefill_last_name: str,
        prefill_email: str,
        signup_source: str,
    ):
        return render_template(
            "pages/auth/quick_signup.html",
            next_url=next_url,
            global_item_id=global_item_id,
            global_item_name=global_item_name,
            prefill_first_name=prefill_first_name,
            prefill_last_name=prefill_last_name,
            prefill_email=prefill_email,
            signup_source=signup_source,
            **quick_signup_page_context,
        )

    if request.method == "POST":
        next_url = _safe_next_path(request.form.get("next")) or url_for(
            "inventory.list_inventory"
        )
        global_item_id = (request.form.get("global_item_id") or "").strip()
        signup_source = _normalize_signup_source(
            request.form.get("source"),
            fallback=("GIL_dashboard_cta" if global_item_id else "quick_signup"),
        )

        trap_value = (request.form.get("website") or "").strip()
        if trap_value:
            trap_email = (request.form.get("email") or "").strip().lower() or None
            PublicBotTrapService.record_hit(
                request=request,
                source=signup_source,
                reason="honeypot",
                email=trap_email,
                extra={"field": "website"},
                block=False,
            )
            if trap_email:
                blocked_user_id = PublicBotTrapService.block_email_if_user_exists(
                    trap_email
                )
                PublicBotTrapService.add_block(
                    email=trap_email, user_id=blocked_user_id
                )
            else:
                PublicBotTrapService.add_block(
                    ip=PublicBotTrapService.resolve_request_ip(request),
                )
            return redirect(url_for("auth.login", next=next_url))

        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = User.normalize_email(request.form.get("email")) or ""
        password = (request.form.get("password") or "").strip()

        if not first_name:
            flash("Please enter your first name.", "error")
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )
        if not last_name:
            flash("Please enter your last name.", "error")
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )

        if PublicBotTrapService.is_blocked(
            ip=PublicBotTrapService.resolve_request_ip(request),
            email=email,
        ):
            PublicBotTrapService.record_hit(
                request=request,
                source=signup_source,
                reason="blocked",
                email=email,
                extra={"flow": "quick_signup"},
                block=False,
            )
            return redirect(url_for("auth.login", next=next_url))

        if not password or len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )

        if User.email_exists(email):
            flash(
                "An account with that email already exists. Please log in instead.",
                "error",
            )
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )

        try:
            tier = _resolve_free_tools_tier()
            verification_enabled = EmailService.should_issue_verification_tokens()
            user, org = AuthLoginRouteService.create_quick_signup_user_and_org(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                signup_source=signup_source,
                tier=tier,
                verification_enabled=verification_enabled,
            )

            quick_signup_completion_properties = {
                "signup_source": signup_source,
                "signup_flow": "quick_signup",
                "billing_provider": "none",
                "tier_id": getattr(tier, "id", None),
                "is_oauth_signup": False,
                "purchase_completed": False,
                "account_origin": "free_quick_signup",
                **AnalyticsTrackingService.build_code_usage_properties(),
            }
            AnalyticsTrackingService.emit_quick_signup_completion_bundle(
                organization_id=org.id,
                user_id=user.id,
                entity_id=org.id,
                completion_properties=quick_signup_completion_properties,
            )

            login_user(user)
            SessionService.rotate_user_session(user)
            session["onboarding_welcome"] = True
            session.pop("onboarding_welcome_flash_shown", None)
            session.pop("onboarding_completion_required_notice", None)
            return redirect(next_url)
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/auth/login_routes.py:701",
                exc_info=True,
            )
            AuthLoginRouteService.rollback_session()
            logger.error("Quick signup failed: %s", exc, exc_info=True)
            flash("Unable to create your account right now. Please try again.", "error")
            return _render_quick_signup_form(
                next_url=next_url,
                global_item_id=global_item_id,
                global_item_name=(request.form.get("global_item_name") or "").strip(),
                prefill_first_name=first_name,
                prefill_last_name=last_name,
                prefill_email=email,
                signup_source=signup_source,
            )

    next_url = _safe_next_path(request.args.get("next")) or url_for(
        "inventory.list_inventory"
    )
    global_item_id = (request.args.get("global_item_id") or "").strip()
    global_item_name = ""
    try:
        if global_item_id and global_item_id.isdigit():
            gi = AuthLoginRouteService.get_global_item_by_id(
                global_item_id=int(global_item_id)
            )
            global_item_name = getattr(gi, "name", "") if gi else ""
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/login_routes.py:723",
            exc_info=True,
        )
        global_item_name = ""
    signup_source = _normalize_signup_source(
        request.args.get("source"),
        fallback=("GIL_dashboard_cta" if global_item_id else "quick_signup"),
    )

    return _render_quick_signup_form(
        next_url=next_url,
        global_item_id=global_item_id,
        global_item_name=global_item_name,
        prefill_first_name="",
        prefill_last_name="",
        prefill_email="",
        signup_source=signup_source,
    )


# --- Logout route ---
# Purpose: Clear scoped session state and invalidate the current session token.
# Inputs: Authenticated session context and current user.
# Outputs: Cleared session/login state with redirect to homepage.
@auth_bp.route("/logout")
def logout():
    session.pop("dev_selected_org_id", None)
    session.pop("dismissed_alerts", None)

    try:
        session.pop("tool_draft", None)
        session.pop("tool_draft_meta", None)
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/login_routes.py:752",
            exc_info=True,
        )
        pass

    if current_user.is_authenticated:
        current_user.active_session_token = None
        try:
            AuthLoginRouteService.commit_session()
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/auth/login_routes.py:759",
                exc_info=True,
            )
            AuthLoginRouteService.rollback_session()

    SessionService.clear_session_state()
    logout_user()
    return redirect(url_for("core.homepage"))
