from ..models import Unit
import logging
from logging.handlers import RotatingFileHandler
import os

# Set up logger for this module
logger = logging.getLogger(__name__)

def setup_logging(app):
    if not os.path.exists('logs'):
        os.makedirs('logs')

    file_handler = RotatingFileHandler('logs/batchtrack.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('BatchTrack startup')

def get_global_unit_list():
    """Get list of all active units, including both standard and organization-specific custom units"""
    logger.info("Getting global unit list")

    try:
        from flask_login import current_user
        from ..models import Unit

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
        units = query.order_by(Unit.type, Unit.name).all()

        if not units:
            logger.warning("No units found, creating fallback units")
            # Create fallback units if none exist
            fallback_units = [
                FallbackUnit('oz', 'oz', 'weight'),
                FallbackUnit('g', 'g', 'weight'),
                FallbackUnit('lb', 'lb', 'weight'),
                FallbackUnit('ml', 'ml', 'volume'),
                FallbackUnit('fl oz', 'fl oz', 'volume'),
                FallbackUnit('count', 'count', 'count')
            ]
            return fallback_units

        return units

    except Exception as e:
        logger.error(f"Error getting global unit list: {e}")
        # Return fallback units on error
        return [
            FallbackUnit('oz', 'oz', 'weight'),
            FallbackUnit('g', 'g', 'weight'),
            FallbackUnit('count', 'count', 'count')
        ]

def validate_density_requirements(from_unit, to_unit, ingredient=None):
    """
    Validates density requirements for unit conversions
    Returns (needs_density: bool, message: str)
    """
    if from_unit.type == to_unit.type:
        return False, None

    if {'volume', 'weight'} <= {from_unit.type, to_unit.type}:
        if not ingredient:
            return True, "Ingredient context required for volume ↔ weight conversion"

        if ingredient.density:
            return False, None

        if ingredient.category and ingredient.category.default_density:
            return False, None

        return True, f"Density required for {ingredient.name}. Set ingredient density or category."

    return False, None