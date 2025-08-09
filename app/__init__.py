from flask import Flask, redirect, url_for, render_template, g, session
from flask_login import current_user
import os
import logging

# Set up logger once
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load configuration
    app.config.from_object('app.config.Config')
    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    os.makedirs('static/product_images', exist_ok=True)

    # Production security settings
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        _configure_production_security(app)

    # Initialize extensions
    _init_extensions(app)

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

    # Register error handlers
    register_error_handlers(app)

    # Initialize performance monitoring
    from app.utils.performance_monitor import PerformanceMonitor
    PerformanceMonitor.init_app(app)

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
    from .extensions import db, migrate, login_manager, mail, csrf

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

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
    from flask import request, redirect, url_for, g, session, flash, jsonify
    from flask_login import current_user
    from app.models import Organization
    from app.utils.authorization import AuthorizationHierarchy

    # Whitelist patterns for performance
    SKIP_AUTH = {'/static/', '/auth/login', '/auth/logout', '/auth/signup', 
                 '/', '/homepage', '/billing/webhooks/', '/api/waitlist'}

    @app.before_request
    def enforce_auth_and_scope():
        path = request.path
        
        # Skip auth for whitelisted paths
        if any(path.startswith(skip) or path == skip for skip in SKIP_AUTH):
            return

        # Require authentication
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401 if request.is_json else redirect(url_for('auth.login'))

        # Handle developer masquerade
        if current_user.user_type == 'developer':
            if path.startswith(('/developer/', '/auth/')):
                return
                
            org_id = session.get('dev_selected_org_id')
            if not org_id or not Organization.query.get(org_id):
                if not org_id:
                    msg = 'Developer must select organization'
                else:
                    session.pop('dev_selected_org_id', None)
                    msg = 'Selected organization no longer exists'
                
                return jsonify({'error': msg}), 403 if request.is_json else redirect(url_for('developer.organizations'))
            
            g.effective_org_id = org_id
            g.is_developer_masquerade = True
        
        elif not current_user.organization_id:
            return jsonify({'error': 'No organization context'}), 403 if request.is_json else redirect(url_for('auth.logout'))

    @app.before_request 
    def enforce_billing():
        if (request.endpoint and not any(request.endpoint.startswith(x) for x in ['static', 'auth.', 'billing.']) 
            and current_user.is_authenticated and current_user.organization):
            
            has_access, reason = AuthorizationHierarchy.check_organization_access(current_user.organization)
            if not has_access and reason not in ['exempt', 'developer']:
                flash('Subscription required' if reason != 'organization_suspended' else 'Organization suspended', 'error')
                return redirect(url_for('billing.upgrade'))

    @app.after_request
    def security_headers(response):
        if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
            response.headers.update({
                'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY'
            })
        return response

def _register_blueprints(app):
    """Register all application blueprints"""
    from .extensions import csrf
    
    # Blueprint registry - fail fast if import fails
    bp_registry = {
        # Core with prefixes
        ('auth', '/auth'): 'blueprints.auth.routes:auth_bp',
        ('recipes', '/recipes'): 'blueprints.recipes.routes:recipes_bp', 
        ('inventory', '/inventory'): 'blueprints.inventory.routes:inventory_bp',
        ('batches', '/batches'): 'blueprints.batches.routes:batches_bp',
        ('settings', '/settings'): 'blueprints.settings.routes:settings_bp',
        ('organization', '/organization'): 'blueprints.organization.routes:organization_bp',
        
        # Standalone
        ('developer', None): 'blueprints.developer.routes:developer_bp',
        ('api', None): 'blueprints.api.routes:api_bp',
        ('admin', None): 'blueprints.admin.admin_routes:admin_bp',
        
        # Products
        ('products', '/products'): 'blueprints.products.products:products_bp',
        ('billing', None): 'blueprints.billing.routes:billing_bp'
    }
    
    for (name, prefix), import_path in bp_registry.items():
        try:
            module_path, attr = import_path.split(':')
            module = __import__(f'app.{module_path}', fromlist=[attr])
            blueprint = getattr(module, attr)
            
            if prefix:
                app.register_blueprint(blueprint, url_prefix=prefix)
            else:
                app.register_blueprint(blueprint)
                
        except (ImportError, AttributeError) as e:
            logger.warning(f"Failed to register {name} blueprint: {e}")
    
    # Special case: waitlist CSRF exemption
    try:
        from .routes.waitlist_routes import waitlist_bp
        app.register_blueprint(waitlist_bp)
        csrf.exempt(app.view_functions.get('waitlist.join_waitlist'))
    except (ImportError, KeyError):
        pass

# Removed - logic moved to _register_blueprints

def _register_template_context(app):
    """Register template context processors and filters"""
    from .utils.permissions import has_permission, has_role, is_organization_owner
    from .utils.unit_utils import get_global_unit_list
    from .utils.timezone_utils import TimezoneUtils
    
    # Cache static data at startup
    @app.before_first_request
    def cache_static_data():
        try:
            from .models import IngredientCategory
            app._cached_units = get_global_unit_list()
            app._cached_categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        except:
            app._cached_units = []
            app._cached_categories = []

    @app.context_processor
    def inject_core():
        def get_current_org():
            if current_user.is_authenticated:
                return getattr(g, 'effective_org_id', None) or current_user.organization_id
            return None

        return {
            'has_permission': has_permission,
            'has_role': has_role, 
            'is_organization_owner': is_organization_owner,
            'get_current_org': get_current_org,
            'units': getattr(app, '_cached_units', []),
            'categories': getattr(app, '_cached_categories', []),
            'TimezoneUtils': TimezoneUtils
        }

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

def register_error_handlers(app):
    """Register application error handlers"""
    from flask import render_template, jsonify, request, redirect, url_for, flash
    from .utils.api_responses import APIResponse

    error_messages = {
        401: "Authentication required",
        403: "Access denied", 
        404: "Resource not found",
        500: "An unexpected error occurred"
    }

    def handle_error(error_code):
        def handler(error):
            if error_code == 500:
                logger.exception("Internal server error")
            if error_code == 401 and not request.is_json:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            message = error_messages[error_code]
            return (jsonify({'error': message}), error_code) if request.is_json else (render_template(f'errors/{error_code}.html'), error_code)
        return handler

    for code in error_messages:
        app.errorhandler(code)(handle_error(code))