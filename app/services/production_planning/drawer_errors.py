"""
Production Planning Drawer Error Handler

Owns container-planning specific drawer payloads (e.g., missing product density).
"""

from typing import Dict, Any
import uuid
from flask import url_for


def generate_drawer_payload_for_container_error(error_code: str, recipe, **context: Any) -> Dict:
    """
    Build a self-describing drawer_payload for container planning errors that
    are user-fixable via a drawer.
    """
    if error_code == 'MISSING_PRODUCT_DENSITY':
        correlation_id = str(uuid.uuid4())
        # We will prompt for product density at the recipe level and fire an event
        # that allows the auto-fill to retry with the provided density in-session.
        # Redirect the user to the unit manager for now; no separate product density modal
        return {
            'version': '1.0',
            'redirect_url': '/conversion/units',
            'error_type': 'container_planning',
            'error_code': error_code,
            'error_message': 'Missing product density to convert between volume and weight units for container planning',
            'correlation_id': correlation_id
        }

    if error_code == 'YIELD_CONTAINER_MISMATCH':
        correlation_id = str(uuid.uuid4())
        recipe_id = getattr(recipe, 'id', None)
        yield_unit = (context.get('mismatch_context') or {}).get('yield_unit')
        
        logger.info(f"🔍 DRAWER DEBUG: Generating YIELD_CONTAINER_MISMATCH payload for recipe {recipe_id}, yield_unit: {yield_unit}")
        
        from flask import url_for
        modal_url = None
        if recipe_id:
            if yield_unit:
                modal_url = url_for(
                    'drawer_actions.container_unit_mismatch_modal',
                    recipe_id=recipe_id,
                    yield_unit=yield_unit
                )
            else:
                modal_url = url_for(
                    'drawer_actions.container_unit_mismatch_modal',
                    recipe_id=recipe_id
                )

        payload = {
            'version': '1.0',
            'modal_url': modal_url,
            'success_event': 'recipe.yield.updated',
            'error_type': 'container_planning',
            'error_code': error_code,
            'error_message': 'Recipe yield unit does not match any available containers.',
            'correlation_id': correlation_id
        }
        
        logger.info(f"🔍 DRAWER DEBUG: Generated payload: {payload}")
        return payload

    # Unknown/unsupported error code: return minimal info (no drawer)
    return {
        'error_type': 'container_planning',
        'error_code': error_code,
        'error_message': 'Unsupported container planning error'
    }

