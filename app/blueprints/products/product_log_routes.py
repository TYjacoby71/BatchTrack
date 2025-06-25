
<old_str>from flask import Blueprint

product_log_bp = Blueprint('product_log', __name__, template_folder='templates')</old_str>
<new_str>from . import products_bp

product_log_bp = Blueprint('product_log', __name__, template_folder='templates')</new_str>
