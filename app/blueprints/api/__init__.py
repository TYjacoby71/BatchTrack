from flask import Blueprint

api_bp = Blueprint('api', __name__, template_folder='templates')

from . import routes

def init_api(app):
    """Initialize API routes"""
    # This function can be used to register additional API routes
    # that need app context
    pass