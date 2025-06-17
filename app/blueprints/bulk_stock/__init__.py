
from flask import Blueprint

bulk_stock_bp = Blueprint('bulk_stock', __name__, url_prefix='/stock')

from . import routes
