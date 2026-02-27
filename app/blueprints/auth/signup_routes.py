"""Signup and pricing-data auth routes."""

from __future__ import annotations

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

from ...extensions import limiter
from ...services.lifetime_pricing_service import LifetimePricingService
from ...services.oauth_service import OAuthService
from ...services.signup_checkout_service import SignupCheckoutService
from ...services.signup_plan_catalog_service import SignupPlanCatalogService
from . import auth_bp


def load_tiers_config():
    raise RuntimeError(
        "load_tiers_config has been removed. Use DB via SubscriptionTier queries."
    )


def _build_signup_fallback_url(
    *,
    tier: str | None,
    billing_mode: str,
    billing_cycle: str | None,
    lifetime_tier: str | None,
    promo: str | None,
    source: str | None,
    referral_code: str | None,
) -> str:
    """Build a safe fallback URL back to signup with plan selection preserved."""
    params: dict[str, str] = {}
    if tier:
        params["tier"] = str(tier)
    if billing_mode in {"standard", "lifetime"}:
        params["billing_mode"] = billing_mode
    if billing_mode == "standard" and billing_cycle in {"monthly", "yearly"}:
        params["billing_cycle"] = billing_cycle
    if billing_mode == "lifetime" and lifetime_tier:
        params["lifetime_tier"] = str(lifetime_tier)
    if promo:
        params["promo"] = str(promo)
    if source:
        params["source"] = str(source)
    if referral_code:
        params["ref"] = str(referral_code)
    return url_for("core.signup_alias", **params)


def _public_signup_allow_live_pricing_network() -> bool:
    """Return whether public signup reads can fetch live Stripe prices."""
    return bool(
        current_app.config.get("SIGNUP_PUBLIC_ALLOW_LIVE_PRICING_NETWORK", True)
    )


@auth_bp.route("/signup-data")
def signup_data():
    """API endpoint to get available tiers for signup modal."""
    allow_live_pricing_network = _public_signup_allow_live_pricing_network()
    db_tiers = SignupPlanCatalogService.load_customer_facing_tiers()
    available_tiers = SignupPlanCatalogService.build_available_tiers_payload(
        db_tiers,
        include_live_pricing=True,
        allow_live_pricing_network=allow_live_pricing_network,
    )
    lifetime_offers = LifetimePricingService.build_lifetime_offers(
        db_tiers,
        include_live_pricing=True,
        allow_live_pricing_network=allow_live_pricing_network,
    )
    oauth_providers = OAuthService.get_enabled_providers()

    return jsonify(
        {
            "available_tiers": available_tiers,
            "lifetime_offers": lifetime_offers,
            "oauth_available": bool(any(oauth_providers.values())),
            "oauth_providers": oauth_providers,
        }
    )


@auth_bp.route("/signup/checkout")
@limiter.limit("600/minute")
def signup_checkout():
    """Legacy direct-checkout route that now redirects into signup selection flow."""
    if current_user.is_authenticated:
        return redirect(url_for("app_routes.dashboard"))

    selected_tier = request.args.get("tier") or ""
    selected_mode = request.args.get("billing_mode") or "standard"
    if selected_mode not in {"standard", "lifetime"}:
        selected_mode = "standard"

    selected_cycle = request.args.get("billing_cycle") or "monthly"
    if selected_cycle not in {"monthly", "yearly"}:
        selected_cycle = "monthly"

    selected_lifetime_tier = request.args.get("lifetime_tier") or ""
    selected_promo = request.args.get("promo") or ""
    signup_source = request.args.get("source") or "pricing_direct_checkout"
    referral_code = request.args.get("ref")

    fallback_url = _build_signup_fallback_url(
        tier=selected_tier,
        billing_mode=selected_mode,
        billing_cycle=selected_cycle,
        lifetime_tier=selected_lifetime_tier,
        promo=selected_promo,
        source=signup_source,
        referral_code=referral_code,
    )
    return redirect(fallback_url)


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("600/minute")
def signup():
    """Signup flow with standard and lifetime plan modes."""
    if current_user.is_authenticated:
        return redirect(url_for("app_routes.dashboard"))

    allow_live_pricing_network = _public_signup_allow_live_pricing_network()
    signup_context = SignupCheckoutService.build_request_context(
        request=request,
        oauth_user_info=session.get("oauth_user_info"),
        allow_live_pricing_network=allow_live_pricing_network,
    )

    if request.method == "POST":
        result = SignupCheckoutService.process_submission(
            context=signup_context,
            form_data=request.form,
        )
        if result.redirect_url:
            return redirect(result.redirect_url)

        if result.flash_message:
            flash(result.flash_message, result.flash_category)
        view_state = (
            result.view_state
            or SignupCheckoutService.build_initial_view_state(signup_context)
        )
    else:
        view_state = SignupCheckoutService.build_initial_view_state(signup_context)

    oauth_providers = OAuthService.get_enabled_providers()
    template_context = SignupCheckoutService.build_template_context(
        signup_context,
        view_state,
        oauth_available=bool(any(oauth_providers.values())),
        oauth_providers=oauth_providers,
        canonical_url=url_for("core.signup_alias", _external=True),
    )
    return render_template("pages/auth/signup.html", **template_context)
