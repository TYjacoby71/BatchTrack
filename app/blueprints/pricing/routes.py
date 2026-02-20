"""Public pricing route handlers."""

from flask import Blueprint, render_template, request, url_for

from app.services.public_pricing_page_service import PublicPricingPageService

pricing_bp = Blueprint("pricing_routes", __name__)


@pricing_bp.route("/pricing")
def pricing():
    """Render the public pricing and tier comparison page."""
    pricing_context = PublicPricingPageService.build_context(request=request)
    return render_template(
        "pages/public/pricing.html",
        show_public_header=True,
        public_header_signup_source="pricing_start_free_trial",
        lightweight_public_shell=True,
        load_analytics=False,
        load_fontawesome=False,
        load_feedback_widget=False,
        page_title="BatchTrack.com | Pricing for Small-Batch Makers",
        page_description=(
            "Compare Hobbyist, Enthusiast, and Fanatic plans with monthly, yearly, "
            "and limited lifetime launch seats."
        ),
        canonical_url=url_for("pricing_routes.pricing", _external=True),
        page_og_image=url_for(
            "static",
            filename="images/og/batchtrack-pricing-og.svg",
            _external=True,
        ),
        **pricing_context,
    )
