from app.blueprints.api.unit_routes import unit_routes as unit_routes_bp
from app.blueprints.api.drawer_actions import drawer_actions as drawer_actions_bp
from app.blueprints.conversion.routes import conversion as conversion_bp
from app.utils.template_filters import register_template_filters
from app.services.conversion_wrapper import ConversionWrapper
from app.services.inventory_adjustment._edit_logic import inventory_adjustment_edit_logic
from app.services.inventory_adjustment._core import inventory_adjustment_core
from app.services.stock_check.handlers.container_handler import container_handler
from app.services.stock_check.handlers.ingredient_handler import ingredient_handler, conversion_drawers
from app.services.batch_service.batch_operations import batch_operations
from app.services.production_planning._container_management import container_management
from app.routes.bulk_stock_routes import bulk_stock_routes as bulk_stock_routes_bp
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.unit_conversion import drawer_errors
from app.services.stock_check.core import stock_check_core


def register_blueprints(app):
    app.register_blueprint(unit_routes_bp)
    app.register_blueprint(drawer_actions_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(bulk_stock_routes_bp)


def register_services():
    ConversionEngine()
    ConversionWrapper()
    inventory_adjustment_edit_logic()
    inventory_adjustment_core()
    container_handler()
    ingredient_handler()
    batch_operations()
    container_management()
    stock_check_core()
    drawer_errors()


def register_filters():
    register_template_filters()


def setup_app(app):
    register_blueprints(app)
    register_services()
    register_filters()