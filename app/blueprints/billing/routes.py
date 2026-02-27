"""Billing and subscription routes.

Synopsis:
Handles upgrade flows, checkout initiation, downgrade selection, and billing webhooks.

Glossary:
- Tier: Subscription plan with limits and permissions.
- Add-on: Optional entitlement purchased or included by tier.
"""

import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user

from ...extensions import csrf, db, limiter
from ...models.models import Organization
from ...models.subscription_tier import SubscriptionTier
from ...services.analytics_tracking_service import AnalyticsTrackingService
from ...services.billing_service import BillingService
from ...services.session_service import SessionService
from ...services.signup_service import SignupService
from ...services.subscription_downgrade_service import (
    apply_downgrade_selection,
    build_downgrade_context,
)
from ...services.whop_service import WhopService
from ...utils.analytics_timing import seconds_since_first_landing
from ...utils.permissions import require_permission
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


# =========================================================
# UPGRADE & CHECKOUT
# =========================================================
# --- Upgrade page ---
# Purpose: Show upgrade options and current tier context.
# Inputs: Authenticated organization context and pricing service responses.
# Outputs: Rendered upgrade template or redirect with flash on missing org.
@billing_bp.route("/upgrade")
@login_required
@require_permission("organization.manage_billing")
def upgrade():
    """Display upgrade options with live pricing"""
    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("app_routes.dashboard"))

    # Get live pricing data
    try:
        pricing_data = BillingService.get_comprehensive_pricing_data()
        logger.info(
            f"Live pricing data retrieved for upgrade page: {len(pricing_data.get('tiers', {}))} tiers"
        )
    except Exception as e:
        logger.error(f"Error fetching live pricing: {e}")
        flash(
            "Pricing information temporarily unavailable. Please try again later.",
            "warning",
        )
        pricing_data = {"tiers": {}, "available": False}

    # Get current tier information
    current_tier = BillingService.get_tier_for_organization(organization)

    # Get subscription details (mock for now since we don't have Stripe integration active)
    subscription_details = {
        "status": "active" if current_tier != "exempt" else "inactive",
        "next_billing_date": None,
        "amount": None,
        "interval": None,
        "trial_end": None,
        "cancel_at_period_end": False,
    }

    # Build a minimal tiers map from DB for debug display (no JSON reads)
    from ...models.subscription_tier import SubscriptionTier

    try:
        db_tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
        tiers_config = {
            str(t.id): {
                "name": t.name,
                "is_available": t.has_valid_integration or t.is_billing_exempt,
                "billing_provider": t.billing_provider,
            }
            for t in db_tiers
        }
    except Exception as e:
        logger.error(f"Error loading tiers from DB: {e}")
        tiers_config = {}

    return render_template(
        "billing/upgrade.html",
        organization=organization,
        pricing_data=pricing_data.get("tiers", {}),
        tiers=tiers_config,
        current_tier=current_tier,
        subscription_details=subscription_details,
    )


# --- Storage add-on checkout ---
# Purpose: Start the legacy storage add-on checkout if allowed.
# Inputs: Authenticated organization/tier state and add-on lookup metadata.
# Outputs: Redirect to checkout session URL or back to billing surfaces.
@billing_bp.route("/storage")
@login_required
@require_permission("organization.manage_billing")
def storage_addon():
    """Redirect to Stripe subscription checkout for storage add-on if configured on the tier."""
    organization = current_user.organization
    if not organization or not organization.subscription_tier:
        flash("No organization or tier found", "error")
        return redirect(url_for("app_routes.dashboard"))

    tier = organization.subscription_tier
    # Enforce tier-allowed add-ons: storage key must be allowed on this tier
    try:
        from ...models.addon import Addon

        storage_addon = Addon.query.filter_by(key="storage", is_active=True).first()
    except Exception:
        storage_addon = None
    if not storage_addon or storage_addon not in getattr(tier, "allowed_addons", []):
        flash(
            "Storage add-on is not available for your tier. Please upgrade instead.",
            "warning",
        )
        return redirect(url_for("billing.upgrade"))

    lookup_key = storage_addon.stripe_lookup_key

    try:
        session = BillingService.create_subscription_checkout_by_lookup_key(
            lookup_key,
            current_user.email,
            success_url=url_for("billing.upgrade", _external=True),
            cancel_url=url_for("billing.upgrade", _external=True),
            metadata={"addon": "storage"},
        )
        if session and getattr(session, "url", None):
            return redirect(session.url)
        flash("Unable to start storage checkout", "error")
    except Exception as e:
        logger.error(f"Storage add-on checkout error: {e}")
        flash("Checkout failed. Please try again later.", "error")
    return redirect(url_for("billing.upgrade"))


# --- Add-on checkout ---
# Purpose: Start checkout for an allowed add-on.
# Inputs: Add-on key path parameter and authenticated org/tier context.
# Outputs: Redirect to provider checkout URL or billing/settings fallback.
@billing_bp.route("/addons/start/<addon_key>", methods=["POST"])
@login_required
@require_permission("organization.manage_billing")
def start_addon_checkout(addon_key):
    """Start Stripe checkout for a specific add-on by key (uses addon.stripe_lookup_key).
    Enforces that the add-on is allowed for the organization's current tier.
    """
    from ...models.addon import Addon

    addon = Addon.query.filter_by(key=addon_key, is_active=True).first()
    if not addon or not addon.stripe_lookup_key:
        flash("Add-on not available.", "warning")
        return redirect(url_for("settings.index") + "#billing")

    organization = current_user.organization
    tier = getattr(organization, "subscription_tier_obj", None)
    # Enforce allowed vs included semantics
    if not tier:
        flash("No subscription tier found for your organization.", "warning")
        return redirect(url_for("settings.index") + "#billing")
    included = set(getattr(tier, "included_addons", []) or [])
    allowed = set(getattr(tier, "allowed_addons", []) or [])
    if addon in included:
        flash("This add-on is already included in your tier.", "info")
        return redirect(url_for("settings.index") + "#billing")
    if addon not in allowed:
        flash("This add-on is not available for your current tier.", "warning")
        return redirect(url_for("billing.upgrade"))

    try:
        session = BillingService.create_subscription_checkout_by_lookup_key(
            addon.stripe_lookup_key,
            current_user.email,
            success_url=url_for("settings.index", _external=True) + "#billing",
            cancel_url=url_for("settings.index", _external=True) + "#billing",
            metadata={
                "addon": (
                    addon.function_key if hasattr(addon, "function_key") else addon.name
                )
            },
        )
        if session and getattr(session, "url", None):
            return redirect(session.url)
        flash("Unable to start checkout", "error")
    except Exception as e:
        logger.error(f"Addon checkout error ({addon_key}): {e}")
        flash("Checkout failed. Please try again later.", "error")
    return redirect(url_for("settings.index") + "#billing")


# =========================================================
# TIER CHECKOUT & DOWNGRADE
# =========================================================
# --- Tier checkout ---
# Purpose: Start tier checkout (optionally with billing cycle).
# Inputs: Target tier identifier, optional billing cycle, and org billing state.
# Outputs: Redirect to checkout URL, downgrade gating screen, or upgrade fallback.
@billing_bp.route("/checkout/<tier>")
@billing_bp.route("/checkout/<tier>/<billing_cycle>")
@login_required
@require_permission("organization.manage_billing")
def checkout(tier, billing_cycle="month"):
    """Initiate checkout process"""
    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("billing.upgrade"))

    try:
        target_tier = SubscriptionTier.find_by_identifier(tier)
        if not target_tier:
            flash("Checkout not available for this tier", "error")
            return redirect(url_for("billing.upgrade"))

        downgrade_context = build_downgrade_context(organization, target_tier)
        limit = downgrade_context.get("limit")
        if limit is not None:
            active_count = len(downgrade_context.get("active_recipes") or [])
            if active_count > limit:
                return redirect(
                    url_for("billing.downgrade", tier=tier, billing_cycle=billing_cycle)
                )

        # Use unified billing service for checkout
        checkout_session = BillingService.create_checkout_session(
            tier,
            current_user.email,
            f"{current_user.first_name} {current_user.last_name}",
            url_for("billing.complete_signup_from_stripe", _external=True),
            url_for("billing.upgrade", _external=True),
            metadata={"tier": tier, "billing_cycle": billing_cycle},
            existing_customer_id=getattr(organization, "stripe_customer_id", None),
        )

        if checkout_session:
            AnalyticsTrackingService.track_billing_checkout_started(
                organization_id=getattr(organization, "id", None),
                user_id=getattr(current_user, "id", None),
                tier=tier,
                billing_cycle=billing_cycle,
                checkout_provider="stripe",
                seconds_since_first_landing=seconds_since_first_landing(request),
            )
            return redirect(checkout_session.url)

        flash("Checkout not available for this tier", "error")
        return redirect(url_for("billing.upgrade"))

    except Exception as e:
        logger.error(f"Checkout error: {e}")
        flash("Checkout failed. Please try again.", "error")
        return redirect(url_for("billing.upgrade"))


# --- Downgrade selection ---
# Purpose: Collect recipe selections before downgrade checkout.
# Inputs: Target tier + billing cycle params and optional recipe selection POST data.
# Outputs: Rendered downgrade template or redirects into checkout/upgrade flow.
@billing_bp.route("/downgrade/<tier>", methods=["GET", "POST"])
@billing_bp.route("/downgrade/<tier>/<billing_cycle>", methods=["GET", "POST"])
@login_required
@require_permission("organization.manage_billing")
def downgrade(tier, billing_cycle="month"):
    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("billing.upgrade"))

    target_tier = SubscriptionTier.find_by_identifier(tier)
    if not target_tier:
        flash("Invalid subscription tier selected", "error")
        return redirect(url_for("billing.upgrade"))

    context = build_downgrade_context(organization, target_tier)
    limit = context.get("limit")
    if limit is None:
        return redirect(
            url_for("billing.checkout", tier=tier, billing_cycle=billing_cycle)
        )

    if request.method == "POST":
        selected_ids = request.form.getlist("keep_recipe_ids")
        success, message = apply_downgrade_selection(
            organization,
            target_tier,
            [int(val) for val in selected_ids if str(val).isdigit()],
            user_id=getattr(current_user, "id", None),
        )
        if not success:
            flash(message, "error")
        else:
            flash(message, "success")
            return redirect(
                url_for("billing.checkout", tier=tier, billing_cycle=billing_cycle)
            )

    return render_template(
        "billing/downgrade_recipes.html",
        organization=organization,
        target_tier=target_tier,
        required_count=context.get("required_count"),
        limit=limit,
        active_recipes=context.get("active_recipes"),
        locked_ids=set(context.get("locked_ids") or []),
        billing_cycle=billing_cycle,
    )


# =========================================================
# PROVIDER CHECKOUTS & CALLBACKS
# =========================================================
# --- Whop checkout ---
# Purpose: Redirect to Whop checkout flow.
# Inputs: Whop product id path parameter and authenticated org/user context.
# Outputs: Redirect to Whop checkout URL or billing upgrade fallback.
@billing_bp.route("/whop-checkout/<product_id>")
@login_required
@require_permission("organization.manage_billing")
def whop_checkout(product_id):
    """Redirect to Whop checkout"""
    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("billing.upgrade"))

    try:
        checkout_url = WhopService.create_checkout_session(
            product_id,
            current_user.email,
            success_url=url_for("billing.complete_signup_from_whop", _external=True),
        )
        if checkout_url:
            return redirect(checkout_url)

        flash("Whop checkout not available", "error")
        return redirect(url_for("billing.upgrade"))

    except Exception as e:
        logger.error(f"Whop checkout error: {e}")
        flash("Checkout failed. Please try again.", "error")
        return redirect(url_for("billing.upgrade"))


# --- Stripe signup completion ---
# Purpose: Finalize signup after Stripe checkout.
# Inputs: Stripe `session_id` query parameter and checkout provisioning result.
# Outputs: Redirect to login/onboarding/signup with context flash messages.
@billing_bp.route("/complete-signup-from-stripe")
def complete_signup_from_stripe():
    """Complete signup process after Stripe payment"""
    session_id = request.args.get("session_id")
    if not session_id:
        flash("Invalid checkout session", "error")
        return redirect(url_for("core.signup_alias"))

    logger.info("Completing signup for checkout session %s", session_id)

    try:
        result = BillingService.finalize_checkout_session(session_id)
    except Exception as exc:
        logger.error("Stripe finalize failed for session %s: %s", session_id, exc)
        flash("Account setup failed. Please contact support.", "error")
        return redirect(url_for("core.signup_alias"))

    organization = None
    owner_user = None
    if isinstance(result, tuple):
        organization, owner_user = result

    if not owner_user:
        flash(
            "Payment confirmed! Please check your inbox for setup instructions.", "info"
        )
        return redirect(url_for("auth.login"))

    ga4_conversion_payload = {
        "transaction_id": str(session_id),
        "currency": "USD",
        "value": None,
        "coupon": (
            str(getattr(organization, "promo_code", "")).strip() or None
            if organization
            else None
        ),
        "tier_id": (
            str(getattr(organization, "subscription_tier_id", "")).strip() or None
            if organization
            else None
        ),
        "tier_name": (
            str(getattr(getattr(organization, "subscription_tier_obj", None), "name", "")).strip()
            or None
            if organization
            else None
        ),
    }
    try:
        checkout_session = BillingService.get_checkout_session(session_id)
        if checkout_session is not None:
            amount_total = getattr(checkout_session, "amount_total", None)
            if amount_total not in (None, ""):
                ga4_conversion_payload["value"] = round(float(amount_total) / 100.0, 2)
            currency_code = str(
                getattr(checkout_session, "currency", "") or ""
            ).strip()
            if currency_code:
                ga4_conversion_payload["currency"] = currency_code.upper()
            metadata = getattr(checkout_session, "metadata", {}) or {}
            if isinstance(metadata, dict):
                coupon_code = str(metadata.get("promo_code") or "").strip()
                if coupon_code:
                    ga4_conversion_payload["coupon"] = coupon_code
    except Exception as exc:
        logger.warning(
            "Unable to enrich GA4 conversion payload for session %s: %s",
            session_id,
            exc,
        )

    login_user(owner_user)
    SessionService.rotate_user_session(owner_user)
    previous_last_login = TimezoneUtils.ensure_timezone_aware(
        getattr(owner_user, "last_login", None)
    )
    owner_user.last_login = TimezoneUtils.utc_now()
    db.session.commit()
    AnalyticsTrackingService.track_user_login_succeeded(
        organization_id=getattr(organization, "id", None),
        user_id=getattr(owner_user, "id", None),
        is_first_login=previous_last_login is None,
        login_method="signup_checkout",
        destination_hint="onboarding_welcome",
        seconds_since_first_landing=seconds_since_first_landing(request),
    )

    session["onboarding_welcome"] = True
    session["ga4_checkout_conversion"] = ga4_conversion_payload
    if owner_user.email and not owner_user.email_verified:
        flash(
            "Please verify your email while you complete account setup.",
            "info",
        )
    return redirect(url_for("onboarding.welcome"))


# --- Whop signup completion ---
# Purpose: Finalize signup after Whop checkout.
# Inputs: Whop `license_key` query parameter and authenticated org context.
# Outputs: Redirect to dashboard/upgrade with activation status messaging.
@billing_bp.route("/complete-signup-from-whop")
@login_required
def complete_signup_from_whop():
    """Complete signup process after Whop payment"""
    try:
        license_key = request.args.get("license_key")
        if not license_key:
            flash("No license key provided", "error")
            return redirect(url_for("billing.upgrade"))

        # Complete signup using Whop license
        success = SignupService.complete_whop_signup(
            current_user.organization, license_key
        )

        if success:
            flash("Subscription activated successfully!", "success")
            return redirect(url_for("app_routes.dashboard"))
        else:
            flash("Failed to activate subscription", "error")
            return redirect(url_for("billing.upgrade"))

    except Exception as e:
        logger.error(f"Whop signup completion error: {e}")
        flash("Signup completion failed", "error")
        return redirect(url_for("billing.upgrade"))


# =========================================================
# ACCOUNT MANAGEMENT
# =========================================================
# --- Customer portal ---
# Purpose: Redirect to the Stripe customer portal.
# Inputs: Authenticated organization billing customer identifier.
# Outputs: Redirect to Stripe customer portal URL or dashboard fallback.
@billing_bp.route("/customer-portal")
@login_required
@require_permission("organization.manage_billing")
def customer_portal():
    """Redirect to Stripe customer portal"""
    organization = current_user.organization
    if not organization or not organization.stripe_customer_id:
        flash("No billing account found", "error")
        return redirect(url_for("app_routes.dashboard"))

    try:
        portal_session = BillingService.create_customer_portal_session(
            organization, url_for("app_routes.dashboard", _external=True)
        )
        if portal_session:
            return redirect(portal_session.url)
        flash("Unable to access billing portal", "error")
    except Exception as e:
        logger.error(f"Customer portal error: {e}")
        flash("Billing portal unavailable", "error")
    return redirect(url_for("app_routes.dashboard"))


# --- Cancel subscription ---
# Purpose: Cancel the current subscription.
# Inputs: Authenticated organization billing provider identifiers.
# Outputs: Redirect to dashboard with success/failure flash messaging.
@billing_bp.route("/cancel-subscription", methods=["POST"])
@login_required
@require_permission("organization.manage_billing")
def cancel_subscription():
    """Cancel current subscription"""
    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("app_routes.dashboard"))

    try:
        if organization.stripe_customer_id:
            success = BillingService.cancel_subscription(
                organization.stripe_customer_id
            )
        elif organization.whop_license_key:
            success = WhopService.cancel_subscription(organization.whop_license_key)
        else:
            flash("No active subscription found", "error")
            return redirect(url_for("app_routes.dashboard"))

        if success:
            flash("Subscription cancelled successfully", "success")
        else:
            flash("Failed to cancel subscription", "error")

    except Exception as e:
        logger.error(f"Subscription cancellation error: {e}")
        flash("Cancellation failed", "error")

    return redirect(url_for("app_routes.dashboard"))


# =========================================================
# WEBHOOKS & DEBUG
# =========================================================
# --- Stripe webhooks ---
# Purpose: Process Stripe webhooks for billing + add-ons.
# Inputs: Raw webhook payload bytes and Stripe signature header.
# Outputs: Empty-body HTTP status responses indicating processing result.
@billing_bp.route("/webhooks/stripe", methods=["POST"])
@csrf.exempt
@limiter.limit("60/minute")
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        logger.error("Stripe webhook secret not configured")
        return "", 500

    try:
        event = BillingService.construct_event(payload, sig_header, webhook_secret)
        logger.info(f"Received Stripe webhook: {event['type']}")

        status = BillingService.handle_webhook_event("stripe", event)
        return "", status

    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        return "", 400
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return "", 400

# --- Handle subscription change ---
# Purpose: Apply subscription created/updated webhook payload status to org records.
# Inputs: Stripe subscription event dictionary with customer/status metadata.
# Outputs: JSON status payload with HTTP status indicating processing outcome.
def handle_subscription_change(event):
    """Handle subscription creation or update"""
    try:
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        status = subscription.get("status")

        organization = Organization.query.filter_by(
            stripe_customer_id=customer_id
        ).first()
        if not organization:
            logger.warning(f"Organization not found for customer ID: {customer_id}")
            return jsonify({"error": "Organization not found"}), 404

        # Update subscription status
        if status in ["active", "trialing"]:
            organization.subscription_status = status
            organization.billing_status = "active"
        elif status == "past_due":
            organization.subscription_status = status
            organization.billing_status = "past_due"
        elif status == "canceled":
            organization.subscription_status = status
            organization.billing_status = "cancelled"

        db.session.commit()
        logger.info(
            f"Updated organization {organization.id} subscription status to {status}"
        )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error handling subscription change: {e}")
        return jsonify({"error": "Processing failed"}), 500

# --- Handle subscription deletion ---
# Purpose: Apply subscription deletion webhook payload status to org records.
# Inputs: Stripe subscription event dictionary with customer metadata.
# Outputs: JSON status payload with HTTP status indicating processing outcome.
def handle_subscription_deleted(event):
    """Handle subscription deletion"""
    try:
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")

        organization = Organization.query.filter_by(
            stripe_customer_id=customer_id
        ).first()
        if not organization:
            logger.warning(f"Organization not found for customer ID: {customer_id}")
            return jsonify({"error": "Organization not found"}), 404

        organization.subscription_status = "cancelled"
        organization.billing_status = "cancelled"
        db.session.commit()
        logger.info(
            f"Updated organization {organization.id} subscription status to cancelled"
        )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")
        return jsonify({"error": "Processing failed"}), 500


# --- Billing debug ---
# Purpose: Provide developer billing debug payload.
# Inputs: Authenticated developer context and active organization billing state.
# Outputs: Rendered billing debug template or redirect on authorization failure.
@billing_bp.route("/debug")
@login_required
@require_permission("organization.manage_billing")
def debug_billing():
    """Debug billing information"""
    if not current_user.is_developer:
        flash("Access denied", "error")
        return redirect(url_for("app_routes.dashboard"))

    organization = current_user.organization
    if not organization:
        flash("No organization found", "error")
        return redirect(url_for("app_routes.dashboard"))

    debug_info = {
        "organization_id": organization.id,
        "subscription_tier": (
            str(organization.subscription_tier_obj.id)
            if organization.subscription_tier_obj
            else None
        ),
        "stripe_customer_id": organization.stripe_customer_id,
        "whop_license_key": organization.whop_license_key,
        "billing_status": getattr(organization, "billing_status", "unknown"),
        "last_online_sync": (
            organization.last_online_sync.isoformat()
            if organization.last_online_sync
            else None
        ),
    }

    return render_template("billing/debug.html", debug_info=debug_info)
