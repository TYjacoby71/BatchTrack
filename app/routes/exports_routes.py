"""Compatibility shim for moved export routes.

Route implementations now live in app.blueprints.exports.routes.
"""

from app.blueprints.exports.routes import exports_bp

__all__ = ["exports_bp"]
