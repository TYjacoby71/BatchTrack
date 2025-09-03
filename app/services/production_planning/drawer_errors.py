"""
Production Planning Drawer Error Handler

Owns container-planning specific drawer payloads (e.g., missing product density).
"""

from typing import Dict
import uuid


def generate_drawer_payload_for_container_error(error_code: str, recipe, from_unit: str, to_unit: str) -> Dict:
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

    # Unknown/unsupported error code: return minimal info (no drawer)
    return {
        'error_type': 'container_planning',
        'error_code': error_code,
        'error_message': 'Unsupported container planning error'
    }

