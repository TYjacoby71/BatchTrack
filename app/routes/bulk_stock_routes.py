"""Compatibility shim for moved bulk stock routes.

Route implementations now live in app.blueprints.bulk_stock.routes.
"""

from app.blueprints.bulk_stock.routes import bulk_stock_bp

__all__ = ["bulk_stock_bp"]