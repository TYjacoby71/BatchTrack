from ..models import Unit
import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from flask import g, current_app
import time

@dataclass(frozen=True)
class FallbackUnit:
    name: str
    aliases: tuple[str, ...] = ()
    to_base_multiplier: float = 1.0

# Set up logger for this module
logger = logging.getLogger(__name__)

def setup_logging(app):
    """Deprecated: logging is configured via app.logging_config.configure_logging."""
    logger.debug('setup_logging called (deprecated). Using centralized logging_config instead.')

def get_global_unit_list():
    """Get list of all active units, including both standard and organization-specific custom units"""
    # Check for request-level cache first
    cache_key = 'global_unit_list'
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    
    # Only log occasionally to reduce noise
    import random
    if random.random() < 0.1:  # Log only 10% of calls
        logger.debug("Getting global unit list")

    try:
        from flask_login import current_user
        from ..models import Unit

        start_time = time.time()
        
        # Base query for active units
        query = Unit.query.filter_by(is_active=True)

        # If user is authenticated, include their organization's custom units
        if current_user and current_user.is_authenticated:
            if current_user.organization_id:
                # Regular user: show standard units + their org's custom units
                query = query.filter(
                    (Unit.is_custom == False) |
                    (Unit.organization_id == current_user.organization_id)
                )
            elif current_user.user_type == 'developer':
                # Developer: check for selected organization
                from flask import session
                selected_org_id = session.get('dev_selected_org_id')
                if selected_org_id:
                    query = query.filter(
                        (Unit.is_custom == False) |
                        (Unit.organization_id == selected_org_id)
                    )
                # Otherwise show all units for system-wide developer access
            else:
                # User without organization: only show standard units
                query = query.filter(Unit.is_custom == False)
        else:
            # Unauthenticated: only show standard units
            query = query.filter(Unit.is_custom == False)

        # Order by type and name for consistent display
        units = query.order_by(Unit.unit_type, Unit.name).all()
        
        # Monitor query performance
        query_time = time.time() - start_time
        if query_time > 0.1:  # Log queries taking > 100ms
            logger.warning(f"Slow unit query: {query_time:.3f}s")

        # Cache the result for this request
        setattr(g, cache_key, units)

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