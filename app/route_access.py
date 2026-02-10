"""Declarative route-access configuration consumed by middleware."""

from __future__ import annotations

from typing import Iterable, Tuple


class RouteAccessConfig:
    """Single source of truth for public/developer/monitoring routes."""

    PUBLIC_ENDPOINTS: Tuple[str, ...] = (
        "static",
        "homepage",
        "index",
        "public_page",
        "auth.login",
        "auth.signup",
        "auth.logout",
        "auth.quick_signup",
        "auth.oauth_google",
        "auth.oauth_callback",
        "auth.oauth_callback_compat",
        "auth.forgot_password",
        "auth.reset_password",
        "auth.resend_verification",
        "auth.verify_email",
        "auth.dev_login",
        "auth.debug_oauth_config",
        "auth.whop_login",
        "auth.signup_data",
        "legal.privacy_policy",
        "legal.terms_of_service",
        "billing.stripe_webhook",
        "billing.complete_signup_from_stripe",
        "billing.complete_signup_from_whop",
        "tools_bp.tools_index",
        "tools_bp.tools_soap",
        "tools_bp.tools_candles",
        "tools_bp.tools_lotions",
        "tools_bp.tools_herbal",
        "tools_bp.tools_baker",
        "tools_bp.tools_draft",
        "exports.soap_inci_tool",
        "exports.candle_label_tool",
        "exports.baker_sheet_tool",
        "exports.lotion_inci_tool",
        "public_api_bp.public_global_item_search",
        "global_library_bp.global_library",
        "global_library_bp.global_item_detail",
        "global_library_bp.global_library_item_stats",
        "recipes.static",
        "recipe_library_bp.recipe_library",
        "recipe_library_bp.recipe_library_detail",
        "recipe_library_bp.organization_marketplace",
        "help_routes.help_overview",
        "help_routes.help_faq",
        "waitlist.join_waitlist",
        "api.health_check",
        "app_routes.vendor_signup",
    )

    PUBLIC_PATH_PREFIXES: Tuple[str, ...] = (
        "/homepage",
        "/legal/",
        "/static/",
        "/favicon.ico",
        "/auth/login",
        "/auth/signup",
        "/auth/logout",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/tools",
        "/tools/",
        "/exports/tool",
        "/api/public",
        "/help",
        "/recipes/library",
    )

    DEVELOPER_ONLY_PATH_PREFIXES: Tuple[str, ...] = ("/developer/",)

    DEVELOPER_NO_ORG_REQUIRED_PREFIXES: Tuple[str, ...] = (
        "/auth/permissions",
        "/global-items",
        "/api/drawers",
    )

    MONITORING_PATHS: Tuple[str, ...] = (
        "/api",
        "/api/",
        "/health",
        "/ping",
    )

    FREQUENT_ENDPOINTS: Tuple[str, ...] = (
        "server_time.get_server_time",
        "api.get_dashboard_alerts",
    )

    @classmethod
    def is_public_endpoint(cls, endpoint: str | None) -> bool:
        return bool(endpoint and endpoint in cls.PUBLIC_ENDPOINTS)

    @classmethod
    def is_public_path(cls, path: str) -> bool:
        return cls._matches_prefix(path, cls.PUBLIC_PATH_PREFIXES)

    @classmethod
    def is_developer_only_path(cls, path: str) -> bool:
        return cls._matches_prefix(path, cls.DEVELOPER_ONLY_PATH_PREFIXES)

    @classmethod
    def is_developer_no_org_required(cls, path: str) -> bool:
        return cls._matches_prefix(path, cls.DEVELOPER_NO_ORG_REQUIRED_PREFIXES)

    @classmethod
    def is_monitoring_request(cls, request) -> bool:
        user_agent = (request.headers.get("User-Agent") or "").lower()
        return (
            user_agent == "node"
            and request.method == "HEAD"
            and request.path in cls.MONITORING_PATHS
        )

    @classmethod
    def should_minimize_logging(cls, endpoint: str | None) -> bool:
        return bool(endpoint and endpoint in cls.FREQUENT_ENDPOINTS)

    @classmethod
    def get_access_summary(cls) -> dict[str, int]:
        return {
            "public_endpoints": len(cls.PUBLIC_ENDPOINTS),
            "public_path_prefixes": len(cls.PUBLIC_PATH_PREFIXES),
            "developer_only_prefixes": len(cls.DEVELOPER_ONLY_PATH_PREFIXES),
            "developer_no_org_prefixes": len(cls.DEVELOPER_NO_ORG_REQUIRED_PREFIXES),
            "monitoring_paths": len(cls.MONITORING_PATHS),
            "frequent_endpoints": len(cls.FREQUENT_ENDPOINTS),
        }

    @staticmethod
    def _matches_prefix(path: str, prefixes: Iterable[str]) -> bool:
        return any(path.startswith(prefix) for prefix in prefixes)
