"""
Production Planning Drawer Error Handler

Owns container-planning specific drawer payloads (e.g., missing product density).
"""

from typing import Dict


def generate_drawer_payload_for_container_error(error_code: str, recipe, from_unit: str, to_unit: str) -> Dict:
    """
    Build a self-describing drawer_payload for container planning errors that
    are user-fixable via a drawer.
    """
    if error_code == 'MISSING_PRODUCT_DENSITY':
        # We will prompt for product density at the recipe level and fire an event
        # that allows the auto-fill to retry with the provided density in-session.
        return {
            'modal_url': f"/api/drawer-actions/containers/product-density-modal/{recipe.id}",
            'success_event': 'productDensityUpdated',
            'error_type': 'container_planning',
            'error_code': error_code,
            'error_message': 'Missing product density to convert between volume and weight units for container planning',
            # Provide structured retry operation for FE-only retry path as a fallback
            'retry_operation': 'container_auto_fill',
            'retry_data': {
                'recipe_id': recipe.id,
                'from_unit': from_unit,
                'to_unit': to_unit
            }
        }

    # Unknown/unsupported error code: return minimal info (no drawer)
    return {
        'error_type': 'container_planning',
        'error_code': error_code,
        'error_message': 'Unsupported container planning error'
    }

