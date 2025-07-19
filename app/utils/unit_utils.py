from ..models import Unit
import logging
from logging.handlers import RotatingFileHandler
import os

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
    """Get comprehensive list of all units in system

    Returns list of unit objects for use in templates and forms.
    Includes both standard units and custom organization units.
    """
    try:
        from flask_login import current_user
        from ..models import Unit

        # Build query for units user can access
        query = Unit.query.filter_by(is_active=True).order_by(Unit.type, Unit.name)

        if current_user and current_user.is_authenticated and current_user.organization_id:
            # Show standard units + organization's custom units
            query = query.filter(
                (Unit.is_custom == False) | 
                (Unit.organization_id == current_user.organization_id)
            )
        else:
            # Only show standard units for unauthenticated users
            query = query.filter_by(is_custom=False)

        units = query.all()
        return units

    except Exception as e:
        # Import here to avoid circular imports in fallback
        try:
            from flask import current_app
            current_app.logger.error(f"Error getting unit list: {str(e)}")
        except:
            pass
        
        # Return basic fallback unit objects (create minimal objects)
        fallback_units = []
        fallback_names = ['g', 'kg', 'oz', 'lb', 'ml', 'l', 'fl oz', 'cup', 'tsp', 'tbsp', 'count']
        
        # Create simple objects with name attribute for template compatibility
        class FallbackUnit:
            def __init__(self, name):
                self.name = name
                
        return [FallbackUnit(name) for name in fallback_names]
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