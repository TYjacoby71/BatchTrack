
from flask import Blueprint

faults_bp = Blueprint('faults', __name__, url_prefix='/logs')

from . import routes
