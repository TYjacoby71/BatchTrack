
from flask import Blueprint, render_template
from flask_login import login_required
from services.fifo_inventory import get_fifo_entries

fifo_bp = Blueprint('fifo', __name__)

@fifo_bp.route('/inventory/<int:inventory_item_id>')
@login_required
def view_fifo_inventory(inventory_item_id):
    entries = get_fifo_entries(inventory_item_id)
    return render_template('fifo/inventory.html', entries=entries)
