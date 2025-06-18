from flask import Blueprint

batches_bp = Blueprint('batches', __name__, template_folder='templates')

from . import routes