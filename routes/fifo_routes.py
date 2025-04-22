
from flask import Blueprint, render_template
from flask_login import login_required
from services.fifo_inventory import get_fifo_inventory

fifo_bp = Blueprint('fifo', __name__)

@fifo_bp.route('/inventory/fifo')
@login_required
def inventory_view():
    inventory = get_fifo_inventory()
    return render_template('fifo_inventory.html', inventory=inventory)
