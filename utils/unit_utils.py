
from models import Unit

def get_global_unit_list():
    """Returns all units ordered by type and custom flag."""
    return Unit.query.order_by(Unit.type, Unit.is_custom, Unit.name).all()
