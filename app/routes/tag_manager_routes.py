"""Compatibility shim for moved tag-manager routes.

Route implementations now live in app.blueprints.tag_manager.routes.
"""

from app.blueprints.tag_manager.routes import tag_manager_bp

__all__ = ["tag_manager_bp"]