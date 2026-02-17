"""Compatibility shim for moved app routes.

Route implementations now live in app.blueprints.dashboard.routes.
"""

from app.blueprints.dashboard.routes import app_routes_bp

__all__ = ["app_routes_bp"]