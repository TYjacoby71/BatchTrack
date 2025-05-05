
from flask import Blueprint, render_template
from flask_login import login_required

fifo_bp = Blueprint('fifo', __name__, template_folder='templates')

@fifo_bp.route('/')
@login_required
def index():
    return render_template('fifo/fifo_inventory.html')
