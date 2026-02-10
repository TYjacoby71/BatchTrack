"""Signup and pricing-data auth routes."""

from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user

from . import auth_bp
from ...extensions import limiter
from ...services.lifetime_pricing_service import LifetimePricingService
from ...services.oauth_service import OAuthService
from ...services.signup_checkout_service import SignupCheckoutService
from ...services.signup_plan_catalog_service import SignupPlanCatalogService


def load_tiers_config():
    raise RuntimeError("load_tiers_config has been removed. Use DB via SubscriptionTier queries.")


@auth_bp.route("/signup-data")
def signup_data():
    """API endpoint to get available tiers for signup modal."""
    db_tiers = SignupPlanCatalogService.load_customer_facing_tiers()
    available_tiers = SignupPlanCatalogService.build_available_tiers_payload(db_tiers)
    lifetime_offers = LifetimePricingService.build_lifetime_offers(db_tiers)

    return jsonify(
        {
            "available_tiers": available_tiers,
            "lifetime_offers": lifetime_offers,
            "oauth_available": OAuthService.is_oauth_configured(),
        }
    )


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("600/minute")
def signup():
    """Signup flow with standard and lifetime plan modes."""
    if current_user.is_authenticated:
        return redirect(url_for("app_routes.dashboard"))

    signup_context = SignupCheckoutService.build_request_context(
        request=request,
        oauth_user_info=session.get("oauth_user_info"),
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
        view_state = result.view_state or SignupCheckoutService.build_initial_view_state(signup_context)
    else:
        view_state = SignupCheckoutService.build_initial_view_state(signup_context)

    template_context = SignupCheckoutService.build_template_context(
        signup_context,
        view_state,
        oauth_available=OAuthService.is_oauth_configured(),
        canonical_url=url_for("auth.signup", _external=True),
    )
    return render_template("pages/auth/signup.html", **template_context)
