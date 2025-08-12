from flask import Blueprint

fifo_bp = Blueprint('fifo', __name__, template_folder='templates')

from . import services

# Import routes if they exist
try:
    from . import routes
except ImportError:
    pass
"""
FIFO Blueprint - INTERNAL USE ONLY

⚠️  Do not import services.py directly from external code.
Use app.services.inventory_adjustment.process_inventory_adjustment() instead.
"""

import warnings

def _warn_direct_import():
    warnings.warn(
        "Direct import of fifo.services is deprecated. "
        "Use app.services.inventory_adjustment.process_inventory_adjustment() instead.",
        DeprecationWarning,
        stacklevel=3
    )

# Monitor for direct imports
import sys
from types import ModuleType

# Store reference to original module before override
_original_module = sys.modules[__name__]

class DeprecatedFIFOModule(ModuleType):
    def __getattr__(self, name):
        if name == 'services':
            _warn_direct_import()
        # Check original module attributes without recursion
        if hasattr(_original_module, name):
            return getattr(_original_module, name)
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Only apply the override if not already applied
if not isinstance(sys.modules.get(__name__), DeprecatedFIFOModule):
    sys.modules[__name__] = DeprecatedFIFOModule(__name__)