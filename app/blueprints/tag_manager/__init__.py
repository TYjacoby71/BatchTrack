
from flask import Blueprint

tag_bp = Blueprint('tag_manager', __name__, template_folder='templates')
tag_manager_bp = tag_bp  # Alias for compatibility

# Routes will be imported when needed
