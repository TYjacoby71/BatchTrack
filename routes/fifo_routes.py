
from flask import Blueprint, render_template
from flask_login import login_required
from services.fifo_inventory import get_fifo_inventory

fifo_bp = Blueprint('fifo', __name__)

# FIFO routes placeholder
