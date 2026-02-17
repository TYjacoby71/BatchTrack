"""Public legal page routes."""

from flask import Blueprint, render_template, url_for

legal_bp = Blueprint("legal", __name__, url_prefix="/legal")


@legal_bp.route("/privacy")
def privacy_policy():
    """Privacy policy page."""
    return render_template(
        "legal/privacy_policy.html",
        show_public_header=True,
        page_title="BatchTrack Privacy Policy",
        page_description="Read how BatchTrack collects, uses, and protects account and production data.",
        canonical_url=url_for("legal.privacy_policy", _external=True),
    )


@legal_bp.route("/terms")
def terms_of_service():
    """Terms of service page."""
    return render_template(
        "legal/terms_of_service.html",
        show_public_header=True,
        page_title="BatchTrack Terms of Service",
        page_description="Review BatchTrack terms governing account access, subscriptions, and acceptable use.",
        canonical_url=url_for("legal.terms_of_service", _external=True),
    )


@legal_bp.route("/cookies")
def cookie_policy():
    """Cookie policy page."""
    return render_template(
        "legal/cookie_policy.html",
        show_public_header=True,
        page_title="BatchTrack Cookie Policy",
        page_description="Understand how BatchTrack uses cookies for authentication, analytics, and product performance.",
        canonical_url=url_for("legal.cookie_policy", _external=True),
    )
