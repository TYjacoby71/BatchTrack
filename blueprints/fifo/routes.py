
from flask import render_template
from flask_login import login_required
from services.fifo_inventory import get_fifo_inventory
from . import fifo_bp

@fifo_bp.route('/inventory')
@login_required
def inventory_view():
    """
    Gets all active FIFO inventory entries ordered by timestamp.
    """
    inventory = get_fifo_inventory()
    return render_template('fifo_inventory.html', inventory=inventory)
