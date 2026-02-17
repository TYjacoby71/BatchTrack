"""Compatibility shim for moved pricing routes.

Route implementations now live in app.blueprints.pricing.routes.
"""

from app.blueprints.pricing.routes import pricing_bp

__all__ = ["pricing_bp"]
