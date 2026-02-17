from flask import Blueprint

production_planning_bp = Blueprint(
    "production_planning", __name__, url_prefix="/production-planning"
)

from . import routes
