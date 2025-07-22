
from flask import Blueprint

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')
print(f"DEBUG: Creating billing blueprint with url_prefix='/billing'")
print(f"DEBUG: billing_bp created: {billing_bp}")

from . import routes
