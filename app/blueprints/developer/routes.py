from flask import Blueprint

from .system_roles import system_roles_bp
from .subscription_tiers import subscription_tiers_bp
from .addons import addons_bp


developer_bp = Blueprint("developer", __name__, url_prefix="/developer")

developer_bp.register_blueprint(system_roles_bp)
developer_bp.register_blueprint(subscription_tiers_bp)
developer_bp.register_blueprint(addons_bp)

# Import view modules for their side effects so routes register with the blueprint.
from . import views  # noqa: F401,E402
