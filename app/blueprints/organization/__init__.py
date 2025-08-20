from flask import Blueprint

organization_bp = Blueprint('organization', __name__, template_folder='templates')

# Import routes to register them with the blueprint
from .routes import organization_bp

__all__ = ['organization_bp']