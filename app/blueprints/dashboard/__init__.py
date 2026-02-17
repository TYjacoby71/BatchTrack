"""Dashboard blueprint package."""

from .routes import app_routes_bp

# Backward-compatible alias for legacy imports.
dashboard_bp = app_routes_bp

__all__ = ["app_routes_bp", "dashboard_bp"]
