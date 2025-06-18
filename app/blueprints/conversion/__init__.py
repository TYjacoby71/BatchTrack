
from flask import Blueprint

conversion_bp = Blueprint('conversion', __name__, template_folder='templates')

from . import routes
from flask import Blueprint

conversion_bp = Blueprint('conversion_bp', __name__, url_prefix='/conversion')

from . import routes
