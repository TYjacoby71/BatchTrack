
"""
Special Operations Handler

Handles special operations that don't fit the additive/deductive pattern
"""

import logging
from app.models import db

logger = logging.getLogger(__name__)

def handle_cost_override_special(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
    """Special handler for cost override (no quantity change)"""
    try:
        if cost_override is not None:
            item.cost_per_unit = cost_override
            db.session.commit()
            return True, f"Updated cost to {cost_override}"
        return False, "No cost override provided"
        
    except Exception as e:
        logger.error(f"Error in cost override: {str(e)}")
        return False, str(e)
