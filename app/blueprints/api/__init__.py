from flask import Blueprint
from .routes import api_bp
from .dashboard_routes import dashboard_api_bp
from .unit_routes import unit_api_bp
from .density_reference import density_reference_bp