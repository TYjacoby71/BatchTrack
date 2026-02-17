"""Compatibility shim for moved landing routes.

Route implementations now live in app.blueprints.landing.routes.
"""

from app.blueprints.landing.routes import landing_pages_bp

__all__ = ["landing_pages_bp"]
