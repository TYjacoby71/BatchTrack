"""Public landing page A/B test routes.

Synopsis:
Serves public maker-first landing variants used for messaging experiments.
Each route passes explicit metadata context to the shared layout template.

Glossary:
- Landing variant: A public page version used in conversion testing.
- Maker-first metadata: Title/description/canonical values aligned to maker intent.
"""

from flask import Blueprint, render_template, url_for

landing_pages_bp = Blueprint("landing_pages", __name__)


# --- Hormozi-style landing page ---
# Purpose: Render the results-first offer page for A/B testing.
@landing_pages_bp.route("/lp/hormozi")
def lp_hormozi():
    """Offer-driven landing page variant (A/B test)."""
    return render_template(
        "pages/public/landing_hormozi.html",
        show_public_header=True,
        lightweight_public_shell=True,
        public_header_is_homepage=True,
        public_header_signup_source="lp_hormozi_header",
        page_title="BatchTrack.com | Results-First System for Small-Batch Makers",
        page_description=(
            "A results-first BatchTrack landing page for makers who need full batch lifecycle tracking, "
            "traceability, FIFO inventory, and calm, neurodivergent-friendly workflows."
        ),
        canonical_url=url_for("landing_pages.lp_hormozi", _external=True),
        page_og_image=url_for(
            "static",
            filename="images/og/batchtrack-default-og.svg",
            _external=True,
        ),
    )


# --- Robbins-style landing page ---
# Purpose: Render the transformation-first calm-maker page for A/B testing.
@landing_pages_bp.route("/lp/robbins")
def lp_robbins():
    """Transformation-driven landing page variant (A/B test)."""
    return render_template(
        "pages/public/landing_robbins.html",
        show_public_header=True,
        lightweight_public_shell=True,
        public_header_is_homepage=True,
        public_header_signup_source="lp_robbins_header",
        page_title="BatchTrack.com | Calm, Inclusive Production Flow for Makers",
        page_description=(
            "A transformation-focused BatchTrack landing page built for neurodivergent small-batch makers "
            "who want calm production systems, full lifecycle traceability, and guided onboarding."
        ),
        canonical_url=url_for("landing_pages.lp_robbins", _external=True),
        page_og_image=url_for(
            "static",
            filename="images/og/batchtrack-default-og.svg",
            _external=True,
        ),
    )
