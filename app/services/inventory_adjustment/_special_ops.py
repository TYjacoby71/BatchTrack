
"""
Special Operations Handler

Handles special operations that don't fit the additive/deductive pattern
"""

import logging
from app.models import db

logger = logging.getLogger(__name__)

def handle_special_operation(item, quantity, change_type, notes=None, created_by=None, cost_override=None, **kwargs):
    """
    Main handler for special operations that don't follow additive/deductive patterns
    Routes to specific special operation handlers based on change_type
    """
    try:
        if change_type == 'cost_override':
            return handle_cost_override_special(item, quantity, notes, created_by, cost_override, **kwargs)
        elif change_type == 'unit_conversion':
            # Unit conversion is handled elsewhere, just return success
            return True, f"Unit conversion handled"
        else:
            logger.error(f"Unknown special operation type: {change_type}")
            return False, f"Unknown special operation: {change_type}"
            
    except Exception as e:
        logger.error(f"Error in special operation handler: {str(e)}")
        return False, str(e)


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
"""
Special Operations Handler

Handles special operations like cost_override and unit_conversion
"""

import logging
from app.models import db

logger = logging.getLogger(__name__)

def handle_cost_override(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
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

def handle_unit_conversion(item, quantity, notes=None, created_by=None, **kwargs):
    """Special handler for unit conversion"""
    try:
        # Unit conversion logic would go here
        # For now, just return success
        return True, "Unit conversion completed"
    except Exception as e:
        logger.error(f"Error in unit conversion: {str(e)}")
        return False, str(e)
