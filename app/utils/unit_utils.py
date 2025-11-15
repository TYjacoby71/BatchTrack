from ..models import Unit
import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from flask import g, current_app
import time
from flask_login import current_user

@dataclass(frozen=True)
class FallbackUnit:
    name: str
    aliases: tuple[str, ...] = ()
    to_base_multiplier: float = 1.0

# Set up logger for this module
logger = logging.getLogger(__name__)
@@ -33,8 +72,12 @@ def get_global_unit_list():
cache_key_full = f"units:{getattr(current_user, 'organization_id', 'public') if hasattr(current_user, 'organization_id') else 'public'}"
    cached_units = app_cache.get(cache_key_full)
    if cached_units:
        setattr(g, cache_key, cached_units)
        return cached_units

    try:
        from ..models import Unit
@@ -71,48 +114,41 @@ def get_global_unit_list():

        # Order by type and name for consistent display
units = query.order_by(Unit.unit_type, Unit.name).all()

        # Monitor query performance
query_time = time.time() - start_time
if query_time > 0.05:  # Log queries taking > 50ms
            logger.warning(f"Unit query took {query_time:.3f}s for {len(units)} units")

        # Cache the result for this request and in app cache
setattr(g, cache_key, units)
app_cache.set(cache_key_full, units, 300)  # 5 minute cache

if not units:
            logger.warning("No units found, creating fallback units")
            # Create fallback units if none exist
            fallback_units = [
                FallbackUnit('oz', ('oz',), 1.0),
                FallbackUnit('g', ('g',), 1.0),
                FallbackUnit('lb', ('lb',), 1.0),
                FallbackUnit('ml', ('ml',), 1.0),
                FallbackUnit('fl oz', ('fl oz',), 1.0),
                FallbackUnit('count', ('count',), 1.0)
            ]
            # Cache fallback units too
            setattr(g, cache_key, fallback_units)
            return fallback_units

return units

except Exception as e:
logger.error(f"Error getting global unit list: {e}")
        # Create fallback unit objects
class FallbackUnitLocal: # Renamed to avoid conflict with the dataclass
            def __init__(self, symbol, name, unit_type):
                self.symbol = symbol
                self.name = name
                self.type = unit_type

        error_fallback = [
            FallbackUnitLocal('g', 'gram', 'weight'),
            FallbackUnitLocal('ml', 'milliliter', 'volume'),
            FallbackUnitLocal('count', 'count', 'quantity')
        ]
        # Cache error fallback too
setattr(g, cache_key, error_fallback)
return error_fallback

def validate_density_requirements(from_unit, to_unit, ingredient=None):
    """
    Validates density requirements for unit conversions
    Returns (needs_density: bool, message: str)
    """
    if from_unit.unit_type == to_unit.unit_type:
        return False, None
    if {'volume', 'weight'} <= {from_unit.unit_type, to_unit.unit_type}:
        if not ingredient:
            return True, "Ingredient context required for volume ↔ weight conversion"
        if ingredient.density:
            return False, None
        if ingredient.category and ingredient.category.default_density:
            return False, None
        return True, f"Density required for {ingredient.name}. Set ingredient density or category."
    return False, None