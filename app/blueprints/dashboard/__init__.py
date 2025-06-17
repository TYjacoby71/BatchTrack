
from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

# Routes will be imported when needed
