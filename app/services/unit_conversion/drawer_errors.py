
"""
Conversion Service Drawer Error Handler

Owns all decisions about when conversion errors require drawers and what type.
This is the single source of truth for conversion error UX decisions.
"""

def handle_conversion_error(conversion_result):
    """
    Convert a ConversionEngine error result into a standardized drawer response.
    
    This is the ONLY place where conversion error -> drawer decisions are made.
    Any service that uses ConversionEngine should call this function.
    """
    if conversion_result.get('success'):
        return {'requires_drawer': False}
    
    error_code = conversion_result.get('error_code')
    error_data = conversion_result.get('error_data', {})
    
    if error_code == 'MISSING_DENSITY':
        return {
            'requires_drawer': True,
            'drawer_type': 'conversion.density_fix',
            'drawer_action': 'open_density_modal',
            'drawer_data': {
                'ingredient_id': error_data.get('ingredient_id'),
                'ingredient_name': error_data.get('ingredient_name'),
                'from_unit': error_data.get('from_unit'),
                'to_unit': error_data.get('to_unit'),
                'api_endpoint': f"/api/drawer-actions/conversion/density-modal/{error_data.get('ingredient_id')}",
                'help_link': '/conversion/units'
            },
            'suggested_density': _get_suggested_density(error_data.get('ingredient_name', '')),
            'error_message': 'Missing density for conversion'
        }
    
    elif error_code == 'MISSING_CUSTOM_MAPPING':
        return {
            'requires_drawer': True,
            'drawer_type': 'conversion.unit_mapping_fix',
            'drawer_action': 'open_unit_mapping_modal',
            'drawer_data': {
                'from_unit': error_data.get('from_unit'),
                'to_unit': error_data.get('to_unit'),
                'api_endpoint': f"/api/drawer-actions/conversion/unit-mapping-modal?from_unit={error_data.get('from_unit')}&to_unit={error_data.get('to_unit')}",
                'unit_manager_link': '/conversion/units'
            },
            'error_message': 'Missing custom unit mapping'
        }
    
    elif error_code in ['UNKNOWN_SOURCE_UNIT', 'UNKNOWN_TARGET_UNIT']:
        return {
            'requires_drawer': True,
            'drawer_type': 'conversion.unit_creation',
            'drawer_action': 'open_unit_creation_modal',
            'drawer_data': {
                'unknown_unit': error_data.get('unit'),
                'unit_manager_link': '/conversion/units'
            },
            'error_message': f'Unknown unit: {error_data.get("unit")}'
        }
    
    elif error_code == 'SYSTEM_ERROR':
        return {
            'requires_drawer': False,
            'error_type': 'system_error',
            'error_message': 'Unit conversion is not available at the moment, please try again'
        }
    
    else:
        # For all other conversion errors, don't show a drawer
        return {
            'requires_drawer': False,
            'error_type': 'conversion_error',
            'error_message': error_data.get('message', 'Conversion failed')
        }

def _get_suggested_density(ingredient_name):
    """Get suggested density for common ingredients"""
    if not ingredient_name:
        return None
        
    density_suggestions = {
        'beeswax': 0.96,
        'wax': 0.93,
        'honey': 1.42,
        'oil': 0.91,
        'water': 1.0,
        'milk': 1.03,
        'butter': 0.92,
        'cream': 0.994,
        'syrup': 1.37
    }
    
    ingredient_lower = ingredient_name.lower()
    for key, density in density_suggestions.items():
        if key in ingredient_lower:
            return density
    return None
