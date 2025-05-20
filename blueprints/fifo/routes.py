
from flask import render_template
from flask_login import login_required
from . import fifo_bp
from .services import get_fifo_entries

@fifo_bp.route('/inventory/<int:inventory_item_id>')
@login_required
def view_fifo_inventory(inventory_item_id):
    entries = get_fifo_entries(inventory_item_id)
    return render_template('fifo/inventory.html', entries=entries)
