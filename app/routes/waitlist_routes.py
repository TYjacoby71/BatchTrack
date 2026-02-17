"""Compatibility shim for moved waitlist routes.

Route implementations now live in app.blueprints.waitlist.routes.
"""

from app.blueprints.waitlist.routes import waitlist_bp

__all__ = ["waitlist_bp"]
