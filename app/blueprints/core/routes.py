"""Core public routes and shared branded asset endpoints.

Synopsis:
Houses app-wide public routes that are not owned by a feature-specific module,
including homepage routing and crawler-facing branding assets.

Glossary:
- Core route: App-level endpoint outside a feature-specific domain.
- Branding asset: Public static SVG used by nav/favicon surfaces.
"""

from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    send_file,
    url_for,
)
from flask_login import current_user

from app.extensions import cache
from app.utils.cache_utils import should_bypass_cache

core_bp = Blueprint("core", __name__)
_BRAND_ASSET_MAX_AGE_SECONDS = 31536000


def _serve_brand_asset(filename: str):
    """Serve attached brand SVG assets used by public templates."""
    asset_path = Path(current_app.root_path).parent / "attached_assets" / filename
    if not asset_path.is_file():
        abort(404)
    response = send_file(
        asset_path,
        mimetype="image/svg+xml",
        max_age=_BRAND_ASSET_MAX_AGE_SECONDS,
    )
    response.cache_control.public = True
    response.cache_control.immutable = True
    return response


def _serve_marketing_public_asset(filename: str, *, mimetype: str):
    """Serve crawler-facing public assets from app/marketing/public."""
    asset_path = Path(current_app.root_path) / "marketing" / "public" / filename
    if not asset_path.is_file():
        abort(404)
    response = send_file(asset_path, mimetype=mimetype, max_age=3600)
    response.cache_control.public = True
    return response


def _serve_cropped_full_logo():
    """Serve a cropped full logo variant sized for navbar display."""
    asset_path = (
        Path(current_app.root_path).parent / "attached_assets" / "Full Logo.svg"
    )
    if not asset_path.is_file():
        abort(404)

    try:
        svg_text = asset_path.read_text(encoding="utf-8")
    except OSError:
        abort(404)

    # Crop excessive whitespace in the exported asset so the header logo is legible.
    svg_text = svg_text.replace(
        'viewBox="0.00 0.00 1024.00 683.00"',
        'viewBox="145 224 735 216"',
        1,
    )
    response = current_app.response_class(svg_text, mimetype="image/svg+xml")
    response.cache_control.public = True
    response.cache_control.max_age = _BRAND_ASSET_MAX_AGE_SECONDS
    response.cache_control.immutable = True
    return response


def _render_public_homepage_response():
    """
    Serve the marketing homepage with Redis caching so anonymous traffic (and load tests)
    avoid re-rendering the full template on every hit.
    """
    cache_key = current_app.config.get(
        "PUBLIC_HOMEPAGE_CACHE_KEY", "public:homepage:v3"
    )
    try:
        from app.utils.settings import is_feature_enabled

        global_library_enabled = is_feature_enabled("FEATURE_GLOBAL_ITEM_LIBRARY")
        cache_key = (
            f"{cache_key}:global_library:{'on' if global_library_enabled else 'off'}"
        )
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


@core_bp.route("/branding/full-logo.svg")
def branding_full_logo():
    """Full horizontal logo used in marketing headers."""
    return _serve_brand_asset("Full Logo.svg")


@core_bp.route("/branding/full-logo-header.svg")
def branding_full_logo_header():
    """Cropped full logo for compact header branding."""
    return _serve_cropped_full_logo()


@core_bp.route("/branding/app-tile.svg")
def branding_app_tile():
    """Square logo tile used for browser icon links."""
    return _serve_brand_asset("App card logo.svg")


@core_bp.route("/sitemap.xml")
def sitemap_xml():
    """XML sitemap for search engine discovery."""
    return _serve_marketing_public_asset("sitemap.xml", mimetype="application/xml")


@core_bp.route("/robots.txt")
def robots_txt():
    """Robots directives for crawlers."""
    return _serve_marketing_public_asset(
        "robots.txt", mimetype="text/plain; charset=utf-8"
    )


@core_bp.route("/llms.txt")
def llms_txt():
    """LLMs.txt guidance for AI crawlers and agents."""
    return _serve_marketing_public_asset(
        "llms.txt", mimetype="text/plain; charset=utf-8"
    )


@core_bp.route("/dev-login")
def dev_login_legacy():
    """Legacy developer-login path kept for backward compatibility."""
    return redirect(url_for("auth.dev_login"), code=301)


@core_bp.route("/")
def index():
    """Main landing page with proper routing logic."""
    if current_user.is_authenticated:
        if current_user.user_type == "developer":
            return redirect(
                url_for("developer.dashboard")
            )  # Developers go to developer dashboard
        return redirect(
            url_for("app_routes.dashboard")
        )  # Regular users go to user dashboard
    return (
        _render_public_homepage_response()
    )  # Serve cached public homepage for unauthenticated users


@core_bp.route("/homepage")
def homepage():
    """Public homepage - accessible to all users."""
    return _render_public_homepage_response()


@core_bp.route("/public")
def public_page():
    """Alternative public page."""
    return _render_public_homepage_response()
