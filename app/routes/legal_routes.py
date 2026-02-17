"""Compatibility shim for moved legal routes.

Route implementations now live in app.blueprints.legal.routes.
"""

from app.blueprints.legal.routes import legal_bp

__all__ = ["legal_bp"]
