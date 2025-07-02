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
    app.logger.info('BatchTrack - Intermediate ingredient work')

def get_global_unit_list():
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            # Get all standard units + user's custom units
            units = Unit.query.filter(
                (Unit.is_custom == False) | 
                (Unit.organization_id == current_user.organization_id)
            ).order_by(Unit.type, Unit.name).all()
        else:
            # Only standard units for unauthenticated users
            units = Unit.query.filter_by(is_custom=False).order_by(Unit.type, Unit.name).all()
        return units
    except Exception as e:
        return []
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
