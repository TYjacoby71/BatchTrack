
"""
Conversion Service Package
Handles all unit conversion logic and error management
"""

from ..unit_conversion import ConversionEngine
from .drawer_errors import should_open_drawer, prepare_density_error_context, prepare_unit_mapping_error_context

__all__ = [
    'ConversionEngine',
    'should_open_drawer', 
    'prepare_density_error_context',
    'prepare_unit_mapping_error_context'
]
