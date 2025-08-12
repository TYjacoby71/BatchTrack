from flask import Flask, redirect, url_for, render_template, g, session
from flask_login import current_user
import os
import logging

# Set up logger once
logger = logging.getLogger(__name__)

def create_app(config=None):
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load default configuration
    app.config.from_object('app.config.Config')

    # Allow tests to override configuration
    if config:
        app.config.update(config)
        # Tests pass DATABASE_URL; SQLAlchemy wants SQLALCHEMY_DATABASE_URI
        if "DATABASE_URL" in config:
            app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]
    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    os.makedirs('static/product_images', exist_ok=True)

    # Production security settings
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        _configure_production_security(app)

    # Initialize extensions
    _init_extensions(app)

    # Initialize limiter with app
    from .extensions import limiter
    limiter.init_app(app)

    # Configure Flask-Login
    _configure_login_manager(app)

    # Register middleware
    _register_middleware(app)

    # Register blueprints
    _register_blueprints(app)

    # Register template context and filters
    _register_template_context(app)

    # Register CLI commands
    from .management import register_commands
    register_commands(app)

    # Add routes
    _add_core_routes(app)

    # Setup logging
    _setup_logging(app)

    return app

def _configure_production_security(app):
    """Configure security settings for production"""
    app.config.update({
        'PREFERRED_URL_SCHEME': 'https',
        'SESSION_COOKIE_SECURE': True,
        'SESSION_COOKIE_HTTPONLY': True,
        'PERMANENT_SESSION_LIFETIME': 1800,
        'SESSION_COOKIE_SAMESITE': 'Lax'
    })

def _init_extensions(app):
    """Initialize Flask extensions"""
    from flask_migrate import Migrate
    from flask_login import LoginManager
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from sqlalchemy.pool import StaticPool
    from .models import db, User

    # Fix SQLite engine options for testing
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if app.config.get("TESTING") or uri.startswith("sqlite"):
        opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        # remove pool args that SQLite memory + StaticPool don't accept
        opts.pop("pool_size", None)
        opts.pop("max_overflow", None)
        if uri == "sqlite:///:memory:":
            opts["poolclass"] = StaticPool
            opts["connect_args"] = {"check_same_thread": False}
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts

    # Initialize database
    db.init_app(app)

    # Initialize extensions
    from .extensions import migrate, login_manager, mail, csrf # limiter is initialized separately

    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    # Limiter is now initialized separately after this function
    # limiter.init_app(app) 

def _configure_login_manager(app):
    """Configure Flask-Login settings"""
    from .extensions import login_manager
    from .models import User

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = app.extensions['sqlalchemy'].session.get(User, int(user_id))
            if user and user.is_active:
                if user.user_type == 'developer':
                    return user
                elif user.organization and user.organization.is_active:
                    return user
            return None
        except (ValueError, TypeError):
            return None

def _register_middleware(app):
    """Register application middleware"""

    @app.before_request
    def enforce_permissions_and_scoping():
        from flask import request, abort, jsonify, session, redirect, url_for, g, flash
        from flask_login import current_user
        from app.models import Organization

        # Optimized path checking with early returns
        path = request.path

        # Fast static file check
        if path.startswith('/static/'):
            return None

        # Auth routes (most common)
        if path.startswith('/auth/'):
            if path in ['/auth/login', '/auth/logout', '/auth/signup']:
                return None

        # Other skip paths
        if path in ['/', '/homepage'] or path.startswith('/billing/webhooks/') or path.startswith('/api/waitlist'):
            return None

        # Require authentication
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

        # Handle developer masquerade
        if current_user.user_type == 'developer':
            if request.path.startswith('/developer/') or request.path.startswith('/auth/'):
                return None

            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                if request.is_json:
                    return jsonify({'error': 'Developer must select organization'}), 403
                flash('Please select an organization to access customer features', 'warning')
                return redirect(url_for('developer.organizations'))

            selected_org = Organization.query.get(selected_org_id)
            if not selected_org:
                session.pop('dev_selected_org_id', None)
                flash('Selected organization no longer exists', 'error')
                return redirect(url_for('developer.organizations'))

            # Set masquerade context
            g.effective_org_id = selected_org_id
            g.effective_org = selected_org
            g.is_developer_masquerade = True

        elif not current_user.organization_id:
            if request.is_json:
                return jsonify({'error': 'No organization context'}), 403
            flash('No organization context available', 'error')
            return redirect(url_for('auth.logout'))

        return None

    @app.before_request
    def force_https():
        from flask import request, redirect
        if (os.environ.get('REPLIT_DEPLOYMENT') == 'true' and 
            not request.is_secure and 
            request.headers.get('X-Forwarded-Proto') != 'https' and
            request.url.startswith('http://')):
            return redirect(request.url.replace('http://', 'https://'), code=301)

    @app.before_request
    def enforce_billing_access():
        from flask import request, session, redirect, url_for, flash
        from flask_login import current_user

        if (request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint.startswith('auth.') or
            request.endpoint.startswith('billing.')
        )):
            return

        if current_user.is_authenticated and current_user.organization:
            from .utils.authorization import AuthorizationHierarchy
            has_access, reason = AuthorizationHierarchy.check_organization_access(current_user.organization)
            if not has_access:
                if reason == 'organization_suspended':
                    flash('Your organization has been suspended. Please contact support.', 'error')
                    return redirect(url_for('billing.upgrade'))
                elif reason not in ['exempt', 'developer']:
                    flash('Subscription required to access the system.', 'error')
                    return redirect(url_for('billing.upgrade'))

    @app.after_request
    def add_security_headers(response):
        if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
            response.headers.update({
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY',
                'X-XSS-Protection': '1; mode=block'
            })
        return response

def _register_blueprints(app):
    """Register all application blueprints"""
    from .extensions import csrf

    # Import blueprints
    blueprints = _import_blueprints()

    # Register core blueprints
    core_registrations = [
        (blueprints['auth_bp'], '/auth'),
        (blueprints['recipes_bp'], '/recipes'),
        (blueprints['inventory_bp'], '/inventory'),
        (blueprints['batches_bp'], '/batches'),
        (blueprints['finish_batch_bp'], '/batches'),
        (blueprints['cancel_batch_bp'], '/batches'),
        (blueprints['start_batch_bp'], '/start-batch'),
        (blueprints['conversion_bp'], '/conversion'),
        (blueprints['expiration_bp'], '/expiration'),
        (blueprints['settings_bp'], '/settings'),
        (blueprints['timers_bp'], '/timers'),
        (blueprints['organization_bp'], '/organization'),
    ]

    for blueprint, prefix in core_registrations:
        if blueprint:
            app.register_blueprint(blueprint, url_prefix=prefix)

    # Register standalone blueprints
    standalone_blueprints = [
        'developer_bp', 'app_routes_bp', 'fifo_bp', 'api_bp', 'admin_bp'
    ]

    for bp_name in standalone_blueprints:
        if blueprints.get(bp_name):
            app.register_blueprint(blueprints[bp_name])

    # Register prefixed blueprints
    prefixed_blueprints = [
        ('add_extra_bp', '/add-extra'),
        ('bulk_stock_bp', '/bulk_stock'),
        ('fault_log_bp', '/fault_log'),
        ('tag_manager_bp', '/tag_manager'),
    ]

    for bp_name, prefix in prefixed_blueprints:
        if blueprints.get(bp_name):
            app.register_blueprint(blueprints[bp_name], url_prefix=prefix)

    # Register waitlist with CSRF exemption
    if blueprints.get('waitlist_bp'):
        app.register_blueprint(blueprints['waitlist_bp'])
        csrf.exempt(app.view_functions['waitlist.join_waitlist'])

    # Register product blueprints
    _register_product_blueprints(app, blueprints)

    # Register API blueprints
    _register_api_blueprints(app, blueprints)

    # Register billing blueprint
    _register_billing_blueprint(app, blueprints)

    # Register legal blueprint
    if blueprints.get('legal_bp'):
        app.register_blueprint(blueprints['legal_bp'])

def _import_blueprints():
    """Import all blueprints with error handling"""
    blueprints = {}

    # Core blueprints - import individually with error handling
    blueprint_imports = [
        ('auth_bp', 'blueprints.auth.routes', 'auth_bp'),
        ('inventory_bp', 'blueprints.inventory.routes', 'inventory_bp'),
        ('recipes_bp', 'blueprints.recipes.routes', 'recipes_bp'),
        ('batches_bp', 'blueprints.batches.routes', 'batches_bp'),
        ('finish_batch_bp', 'blueprints.batches.finish_batch', 'finish_batch_bp'),
        ('start_batch_bp', 'blueprints.batches.start_batch', 'start_batch_bp'),
        ('cancel_batch_bp', 'blueprints.batches.cancel_batch', 'cancel_batch_bp'),
        ('api_bp', 'blueprints.api.routes', 'api_bp'),
        ('settings_bp', 'blueprints.settings.routes', 'settings_bp'),
        ('expiration_bp', 'blueprints.expiration.routes', 'expiration_bp'),
        ('conversion_bp', 'blueprints.conversion.routes', 'conversion_bp'),
        ('organization_bp', 'blueprints.organization.routes', 'organization_bp'),
        ('developer_bp', 'blueprints.developer.routes', 'developer_bp'),
        ('timers_bp', 'blueprints.timers.routes', 'timers_bp'),
        ('app_routes_bp', 'routes.app_routes', 'app_routes_bp'),
        ('fifo_bp', 'blueprints.fifo', 'fifo_bp'),
        ('add_extra_bp', 'blueprints.batches.add_extra', 'add_extra_bp'),
        ('waitlist_bp', 'routes.waitlist_routes', 'waitlist_bp'),
        ('admin_bp', 'blueprints.admin.admin_routes', 'admin_bp'),
        ('legal_bp', 'routes.legal_routes', 'legal_bp'),
    ]

    for bp_key, module_path, bp_name in blueprint_imports:
        try:
            module = __import__(f'app.{module_path}', fromlist=[bp_name])
            blueprints[bp_key] = getattr(module, bp_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Failed to import {bp_key} from {module_path}: {e}")

    # Import route modules with error handling
    try:
        from .routes import bulk_stock_routes, fault_log_routes, tag_manager_routes
        blueprints.update({
            'bulk_stock_bp': bulk_stock_routes.bulk_stock_bp,
            'fault_log_bp': fault_log_routes.fault_log_bp,
            'tag_manager_bp': tag_manager_routes.tag_manager_bp,
        })
    except ImportError as e:
        logger.warning(f"Failed to import route modules: {e}")

    return blueprints

def _register_product_blueprints(app, blueprints):
    """Register product-related blueprints"""
    try:
        from .blueprints.products.products import products_bp
        from .blueprints.products.api import products_api_bp
        from .blueprints.products.product_inventory_routes import product_inventory_bp
        from .blueprints.products.product_variants import product_variants_bp
        from .blueprints.products.sku import sku_bp
        from .blueprints.products.reservation_routes import reservation_bp
        from .blueprints.api.reservation_routes import reservation_api_bp

        app.register_blueprint(products_bp, url_prefix='/products')
        app.register_blueprint(products_api_bp)
        app.register_blueprint(product_inventory_bp, url_prefix='/products')
        app.register_blueprint(product_variants_bp, url_prefix='/products')
        app.register_blueprint(sku_bp, url_prefix='/products')
        app.register_blueprint(reservation_bp, url_prefix='/reservations')
        app.register_blueprint(reservation_api_bp)
    except ImportError:
        logger.warning("Could not register product blueprints")

def _register_api_blueprints(app, blueprints):
    """Register API blueprints"""
    try:
        from .blueprints.api.stock_routes import stock_api_bp
        from .blueprints.api.ingredient_routes import ingredient_api_bp
        from .blueprints.api.container_routes import container_api_bp
        from .blueprints.api.dashboard_routes import dashboard_api_bp
        from .blueprints.api.unit_routes import unit_api_bp

        api_blueprints = [
            stock_api_bp, ingredient_api_bp, container_api_bp, 
            dashboard_api_bp, unit_api_bp
        ]

        for bp in api_blueprints:
            app.register_blueprint(bp)

        # Initialize API routes
        try:
            from .blueprints.api import init_api
            init_api(app)
        except ImportError:
            pass

    except ImportError:
        logger.warning("Could not register API blueprints")

def _register_billing_blueprint(app, blueprints):
    """Register billing blueprint with error handling"""
    try:
        from .blueprints.billing.routes import billing_bp
        app.register_blueprint(billing_bp)
        logger.debug("Billing blueprint registered successfully")
    except Exception as e:
        logger.error(f"Failed to register billing blueprint: {e}")

def _register_template_context(app):
    """Register template context processors and filters"""

    # Import models once
    from .models import Unit, IngredientCategory

    @app.context_processor  
    def inject_units():
        from .utils.unit_utils import get_global_unit_list
        from flask import current_app

        # Cache at app level, not request level
        if not hasattr(current_app, '_cached_units'):
            try:
                current_app._cached_units = get_global_unit_list()
                current_app._cached_categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
            except:
                current_app._cached_units = []
                current_app._cached_categories = []

        return dict(
            units=current_app._cached_units, 
            categories=current_app._cached_categories, 
            global_units=current_app._cached_units
        )

    @app.context_processor
    def inject_permissions():
        from .utils.permissions import has_permission, has_role, is_organization_owner
        from .services.reservation_service import ReservationService
        from .utils.unit_utils import get_global_unit_list
        from .models import ProductSKU

        def get_reservation_summary(inventory_item_id):
            if not inventory_item_id:
                return {'available': 0.0, 'reserved': 0.0, 'total': 0.0, 'reservations': []}

            cache_key = f'reservation_summary_{inventory_item_id}'
            if hasattr(g, cache_key):
                return getattr(g, cache_key)

            sku = ProductSKU.query.filter_by(inventory_item_id=inventory_item_id).first()
            result = ReservationService.get_reservation_summary_for_sku(sku) if sku else {
                'available': 0.0, 'reserved': 0.0, 'total': 0.0, 'reservations': []
            }

            setattr(g, cache_key, result)
            return result

        return dict(
            has_permission=has_permission,
            has_role=has_role,
            is_organization_owner=is_organization_owner,
            get_reservation_summary=get_reservation_summary,
            get_global_unit_list=get_global_unit_list
        )

    @app.context_processor
    def inject_organization_helpers():
        from .models import Organization

        def get_organization_by_id(org_id):
            if org_id:
                try:
                    return app.extensions['sqlalchemy'].session.get(Organization, org_id)
                except:
                    return Organization.query.get(org_id)
            return None

        def get_current_organization():
            if current_user.is_authenticated:
                if current_user.user_type == 'developer':
                    org_id = session.get('dev_selected_org_id')
                else:
                    org_id = current_user.organization_id
                return get_organization_by_id(org_id) if org_id else None
            return None

        return dict(
            get_organization_by_id=get_organization_by_id,
            get_current_organization=get_current_organization
        )

    @app.context_processor
    def inject_timezone_utils():
        from .utils.timezone_utils import TimezoneUtils
        return dict(
            TimezoneUtils=TimezoneUtils,
            TimezoneUtils_global=TimezoneUtils,
            current_time=TimezoneUtils.utc_now
        )

    # Register template globals
    _register_template_globals(app)

    # Register filters
    _register_template_filters(app)

def _register_template_globals(app):
    """Register template global functions"""
    from .utils.permissions import (
        has_permission, has_role, has_subscription_feature, 
        is_organization_owner, is_developer
    )

    def template_has_permission(permission_name):
        try:
            return has_permission(permission_name)
        except Exception as e:
            logger.error(f"Permission check error for {permission_name}: {e}")
            return False

    def template_has_role(role_name):
        try:
            return has_role(role_name)
        except Exception as e:
            logger.error(f"Role check error for {role_name}: {e}")
            return False

    def template_is_org_owner():
        try:
            return is_organization_owner()
        except Exception as e:
            logger.error(f"Org owner check error: {e}")
            return False

    def template_get_org_id():
        try:
            if current_user.is_authenticated:
                if current_user.user_type == 'developer':
                    return session.get('dev_selected_org_id')
                return current_user.organization_id
            return None
        except Exception as e:
            logger.error(f"Organization ID check error: {e}")
            return None

    # Register globals
    app.jinja_env.globals.update({
        'has_permission': template_has_permission,
        'has_role': template_has_role,
        'has_subscription_feature': has_subscription_feature,
        'is_organization_owner': template_is_org_owner,
        'is_developer': is_developer,
        'can_access_route': lambda route_path: True,  # Deprecated but maintained
        'get_effective_org_id': template_get_org_id
    })

def _register_template_filters(app):
    """Register Jinja2 filters"""
    from .filters.product_filters import (
        product_variant_name, ingredient_cost_currency, safe_float,
        register_filters
    )

    # Register product filters
    register_filters(app)

    # Register custom filters
    app.jinja_env.filters.update({
        'product_variant_name': product_variant_name,
        'ingredient_cost_currency': ingredient_cost_currency,
        'safe_float': safe_float
    })

    @app.template_filter('attr_multiply')
    def attr_multiply_filter(item, attr1, attr2):
        if item is None:
            return 0
        val1 = getattr(item, attr1, 0) or 0
        val2 = getattr(item, attr2, 0) or 0
        return float(val1) * float(val2)

def _add_core_routes(app):
    """Add core application routes"""
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                return redirect(url_for('app_routes.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

def _setup_logging(app):
    """Setup application logging"""
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    if not app.debug and not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

    if app.debug:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.DEBUG)

    # Import models to ensure they're registered
    from . import models