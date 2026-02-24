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
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user

from app.extensions import cache
from app.services.public_media_service import (
    build_media_signature,
    get_homepage_feature_cards,
    get_homepage_integration_tiles,
    get_homepage_media_slots,
    get_homepage_more_feature_cards,
    get_homepage_testimonial_media,
)
from app.services.public_tools_service import (
    build_public_tool_flag_signature,
    get_enabled_public_tools,
    get_homepage_balanced_display_tools,
    get_homepage_public_tools,
    get_public_tool_flags,
)
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
    tool_flags = get_public_tool_flags()
    enabled_public_tools = get_enabled_public_tools(tool_flags=tool_flags)
    homepage_tool_cards = get_homepage_public_tools(
        tool_flags=tool_flags,
        max_cards=3,
    )
    homepage_tool_cards_desktop = get_homepage_balanced_display_tools(
        tool_flags=tool_flags,
        max_cards=3,
    )
    homepage_feature_cards = get_homepage_feature_cards()
    homepage_more_feature_cards = get_homepage_more_feature_cards()
    homepage_integration_tiles = get_homepage_integration_tiles()
    homepage_media_slots = get_homepage_media_slots()
    homepage_testimonial_media = get_homepage_testimonial_media()
    try:
        from app.utils.settings import is_feature_enabled

        global_library_enabled = is_feature_enabled("FEATURE_GLOBAL_ITEM_LIBRARY")
        cache_key = (
            f"{cache_key}:global_library:{'on' if global_library_enabled else 'off'}"
        )
    except Exception:
        pass
    try:
        tool_flag_signature = build_public_tool_flag_signature(tool_flags=tool_flags)
        cache_key = f"{cache_key}:tools:{tool_flag_signature}"
    except Exception:
        pass
    try:
        tool_media_signature = build_media_signature(
            (
                str(tool.get("slug") or ""),
                tool.get("media"),
            )
            for tool in homepage_tool_cards_desktop
        )
        cache_key = f"{cache_key}:tool-media:{tool_media_signature or 'none'}"
    except Exception:
        pass
    try:
        feature_media_signature = build_media_signature(
            (
                str(card.get("slug") or ""),
                card.get("media"),
            )
            for card in homepage_feature_cards
        )
        cache_key = f"{cache_key}:feature-media:{feature_media_signature or 'none'}"
    except Exception:
        pass
    try:
        more_feature_media_signature = build_media_signature(
            (
                str(card.get("slug") or ""),
                card.get("media"),
            )
            for card in homepage_more_feature_cards
        )
        cache_key = (
            f"{cache_key}:more-feature-media:{more_feature_media_signature or 'none'}"
        )
    except Exception:
        pass
    try:
        integration_media_signature = build_media_signature(
            (
                str(tile.get("slug") or ""),
                tile.get("media"),
            )
            for tile in homepage_integration_tiles
        )
        cache_key = f"{cache_key}:integration-media:{integration_media_signature or 'none'}"
    except Exception:
        pass
    try:
        testimonial_media_signature = build_media_signature(
            (
                f"{customer_key}:logo",
                (slots.get("logo") if isinstance(slots, dict) else None),
            )
            for customer_key, slots in sorted(homepage_testimonial_media.items())
        )
        testimonial_photo_signature = build_media_signature(
            (
                f"{customer_key}:photo",
                (slots.get("photo") if isinstance(slots, dict) else None),
            )
            for customer_key, slots in sorted(homepage_testimonial_media.items())
        )
        cache_key = (
            f"{cache_key}:testimonial-media:{testimonial_media_signature or 'none'}"
            f":testimonial-photo:{testimonial_photo_signature or 'none'}"
        )
    except Exception:
        pass
    try:
        slot_media_signature = build_media_signature(
            (slot_key, media) for slot_key, media in sorted(homepage_media_slots.items())
        )
        cache_key = f"{cache_key}:page-slots:{slot_media_signature or 'none'}"
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

    rendered = render_template(
        "homepage.html",
        homepage_tool_cards=homepage_tool_cards,
        homepage_tool_cards_desktop=homepage_tool_cards_desktop,
        homepage_feature_cards=homepage_feature_cards,
        homepage_more_feature_cards=homepage_more_feature_cards,
        homepage_integration_tiles=homepage_integration_tiles,
        homepage_media_slots=homepage_media_slots,
        homepage_testimonial_media=homepage_testimonial_media,
        homepage_mobile_swipe_enabled=len(homepage_tool_cards) > 1,
        homepage_has_more_tools=len(enabled_public_tools) > len(homepage_tool_cards),
        homepage_enabled_tool_count=len(enabled_public_tools),
    )
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


@core_bp.route("/signup", methods=["GET", "POST"])
def signup_alias():
    """Public short-path alias that reuses the auth signup flow."""
    from app.blueprints.auth.signup_routes import signup as auth_signup_view

    return auth_signup_view()


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


@core_bp.route("/health", methods=["GET", "HEAD"])
@core_bp.route("/ping", methods=["GET", "HEAD"])
def health_check():
    """Lightweight probe endpoint for load balancers and uptime monitors."""
    if request.method == "HEAD":
        return "", 200
    return jsonify({"status": "ok"})
