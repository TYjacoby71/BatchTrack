
"""
Conversion service drawer error handling
Determines when conversion errors need drawer solutions
"""

def should_open_drawer(error_code, error_data):
    """Determine if a conversion error needs a drawer solution"""
    drawer_requiring_errors = {
        'MISSING_DENSITY',
        'MISSING_CUSTOM_MAPPING', 
        'UNKNOWN_SOURCE_UNIT',
        'UNKNOWN_TARGET_UNIT'
    }
    return error_code in drawer_requiring_errors

def prepare_density_error_context(ingredient_id, error_data):
    """Prepare context for density fix modal"""
    from app.models import InventoryItem
    
    ingredient = InventoryItem.query.get(ingredient_id)
    if not ingredient:
        return None
        
    suggested_density = None
    if ingredient.category and ingredient.category.default_density:
        suggested_density = ingredient.category.default_density
    
    return {
        'ingredient_id': ingredient_id,
        'ingredient_name': ingredient.name,
        'current_density': ingredient.density,
        'suggested_density': suggested_density,
        'from_unit': error_data.get('from_unit'),
        'to_unit': error_data.get('to_unit')
    }

def prepare_unit_mapping_error_context(error_data):
    """Prepare context for unit mapping modal"""
    return {
        'from_unit': error_data.get('from_unit'),
        'to_unit': error_data.get('to_unit'),
        'conversion_factor_hint': error_data.get('suggested_factor', 1.0)
    }

def prepare_unknown_unit_error_context(error_data):
    """Prepare context for unit creation modal"""
    return {
        'unknown_unit': error_data.get('unit'),
        'suggested_type': error_data.get('suggested_type', 'volume'),
        'create_unit_url': '/conversion/units'
    }
