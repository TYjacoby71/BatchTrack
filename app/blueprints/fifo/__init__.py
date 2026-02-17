"""
FIFO Blueprint Stub

This module provides backward compatibility for FIFO-related imports.
All FIFO functionality has been moved to the inventory_adjustment service.
"""

from flask import Blueprint

# Create minimal blueprint
fifo_bp = Blueprint("fifo", __name__)


# Minimal compatibility exports to prevent import errors
def get_fifo_entries(*args, **kwargs):
    """Compatibility stub - use inventory_adjustment service instead"""
    raise NotImplementedError("Use app.services.inventory_adjustment instead")


def get_expired_fifo_entries(*args, **kwargs):
    """Compatibility stub - use inventory_adjustment service instead"""
    raise NotImplementedError("Use app.services.inventory_adjustment instead")


def recount_fifo(*args, **kwargs):
    """Compatibility stub - use inventory_adjustment service instead"""
    raise NotImplementedError("Use app.services.inventory_adjustment instead")


__all__ = ["fifo_bp", "get_fifo_entries", "get_expired_fifo_entries", "recount_fifo"]
