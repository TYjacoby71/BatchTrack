
from flask import Blueprint

faults_bp = Blueprint('faults', __name__, template_folder='templates')

from . import routes
