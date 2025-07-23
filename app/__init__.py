from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from .extensions import db
from .models import User
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import current_user


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production') #os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.makedirs('static/product_images', exist_ok=True)
    os.chmod(instance_path, 0o777)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/product_images'

    # Force HTTPS in production
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        app.config['PREFERRED_URL_SCHEME'] = 'https'
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    # Initialize CSRF protection
    from .extensions import csrf
    csrf.init_app(app)

    # Exempt Stripe webhooks from CSRF protection
    csrf.exempt('billing.stripe_webhook')

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        try:
            user = User.query.get(int(user_id))
            # Ensure user is active
            if user and user.is_active:
                # For developers, organization is not required
                if user.user_type == 'developer':
                    return user
                # For regular users, check organization
                elif user.organization and user.organization.is_active:
                    return user
            return None
        except (ValueError, TypeError):
            return None

    # Comprehensive permission and scoping middleware
    @app.before_request
    def enforce_permissions_and_scoping():
        """Universal permission and organization scoping enforcement"""
        from flask import request, abort, jsonify
        from flask_login import current_user
        from app.utils.permissions import has_permission, get_effective_organization_id
        
        # Skip for static files and auth routes
        if (request.path.startswith('/static/') or 
            request.path.startswith('/auth/login') or 
            request.path.startswith('/auth/logout') or
            request.path == '/' or 
            request.path == '/homepage'):
            return None
            
        # Require authentication for all other routes
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))
        
        # Developer isolation - ensure developers access appropriate routes
        if current_user.user_type == 'developer':
            # Allow developer routes
            if request.path.startswith('/developer/'):
                return None
            # Allow auth routes
            if request.path.startswith('/auth/'):
                return None
            # Require organization filter for customer routes
            if not session.get('dev_selected_org_id'):
                if request.is_json:
                    return jsonify({'error': 'Developer must select organization to access customer features'}), 403
                flash('Please select an organization to access customer features', 'warning')
                return redirect(url_for('developer.organizations'))
        
        # Organization scoping enforcement for all non-developer users
        effective_org_id = get_effective_organization_id()
        if not effective_org_id and current_user.user_type != 'developer':
            if request.is_json:
                return jsonify({'error': 'No organization context'}), 403
            flash('No organization context available', 'error')
            return redirect(url_for('auth.logout'))
        
        # Route-based permission checking
        route_permissions = {
            # Core features
            '/inventory': 'inventory.view',
            '/recipes': 'recipes.view', 
            '/batches': 'batches.view',
            '/products': 'products.view',
            '/timers': 'timers.view',
            
            # Management features
            '/organization': 'organization.view',
            '/auth/permissions': 'dev.system_admin',
            '/auth/roles': 'organization.manage_roles',
            '/tag-manager': 'tags.manage',
            
            # API endpoints
            '/api/batches': 'batches.view',
            '/api/inventory': 'inventory.view',
            '/api/products': 'products.view',
            '/api/timers': 'timers.view',
        }
        
        # Check route permissions
        for route_prefix, required_permission in route_permissions.items():
            if request.path.startswith(route_prefix):
                if not has_permission(required_permission):
                    if request.is_json:
                        return jsonify({'error': f'Permission denied: {required_permission}'}), 403
                    flash(f'Access denied: {required_permission}', 'error')
                    return redirect(url_for('app_routes.dashboard'))
                break
        
        return None

            # Allow access to static files and API routes
            if request.path.startswith('/api/') or request.path.startswith('/static/'):
                return None

            # Allow access to root and homepage
            if request.path in ['/', '/homepage']:
                return None

            # If accessing customer routes, require organization selection
            if not session.get('dev_selected_org_id'):
                flash('Please select an organization to view customer data, or use the developer dashboard.', 'warning')
                return redirect(url_for('developer.dashboard'))

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.products import products_bp
    from .blueprints.products.api import products_api_bp
    from .blueprints.recipes import recipes_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.batches import batches_bp
    from .blueprints.batches.finish_batch import finish_batch_bp
    from .blueprints.batches.cancel_batch import cancel_batch_bp
    from .blueprints.batches.start_batch import start_batch_bp
    from .blueprints.api.stock_routes import stock_api_bp
    from .blueprints.api.ingredient_routes import ingredient_api_bp
    from .blueprints.conversion import conversion_bp
    from .blueprints.expiration import expiration_bp
    from .blueprints.settings import settings_bp
    from .blueprints.timers import timers_bp
    from .blueprints.quick_add import quick_add_bp
    from .blueprints.admin import admin_bp
    from .routes import app_routes
    from .blueprints.fifo import fifo_bp
    from .blueprints.batches.add_extra import add_extra_bp
    from .routes import bulk_stock_routes
    from .routes import fault_log_routes
    from .routes import tag_manager_routes
    # Register admin blueprints
    from .blueprints.admin.admin_routes import admin_bp
    app.register_blueprint(admin_bp)

    # Register developer blueprint
    from .blueprints.developer.routes import developer_bp
    app.register_blueprint(developer_bp)

    # Register reservation blueprints (now under products)
    from .blueprints.products.reservation_routes import reservation_bp
    from .blueprints.api.reservation_routes import reservation_api_bp
    app.register_blueprint(reservation_bp, url_prefix='/reservations')
    app.register_blueprint(reservation_api_bp)

    # Register billing blueprint
    try:
        from .blueprints.billing import billing_bp
        print(f"DEBUG: Billing blueprint imported successfully: {billing_bp}")
        print(f"DEBUG: Billing blueprint name: {billing_bp.name}")
        print(f"DEBUG: Billing blueprint url_prefix: {billing_bp.url_prefix}")
        app.register_blueprint(billing_bp)
        print("DEBUG: Billing blueprint registered successfully")
    except Exception as e:
        print(f"ERROR: Failed to register billing blueprint: {e}")
        import traceback
        traceback.print_exc()

    # Register all blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(finish_batch_bp, url_prefix='/batches')
    app.register_blueprint(cancel_batch_bp, url_prefix='/batches')
    app.register_blueprint(start_batch_bp, url_prefix='/start-batch')
    # Import and register blueprints
    try:
        from .blueprints.products.products import products_bp
        from .blueprints.products.api import products_api_bp
        from .blueprints.products.product_inventory_routes import product_inventory_bp
        from .blueprints.products.product_variants import product_variants_bp
        from .blueprints.products.sku import sku_bp
        app.register_blueprint(products_bp, url_prefix='/products')
        app.register_blueprint(products_api_bp)
        app.register_blueprint(product_inventory_bp, url_prefix='/products')
        app.register_blueprint(product_variants_bp, url_prefix='/products')
        app.register_blueprint(sku_bp, url_prefix='/products')
    except ImportError:
        print("Could not register any product blueprints")
        pass

    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(expiration_bp, url_prefix='/expiration')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(quick_add_bp, url_prefix='/quick_add')
    app.register_blueprint(app_routes.app_routes_bp)
    app.register_blueprint(fifo_bp)
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')
    app.register_blueprint(bulk_stock_routes.bulk_stock_bp, url_prefix='/bulk_stock')
    app.register_blueprint(fault_log_routes.fault_log_bp, url_prefix='/fault_log')
    app.register_blueprint(tag_manager_routes.tag_manager_bp, url_prefix='/tag_manager')

    # Register organization blueprint
    from .blueprints.organization.routes import organization_bp
    app.register_blueprint(organization_bp, url_prefix='/organization')

    # Register API blueprint
    from .blueprints.api import api_bp
    app.register_blueprint(api_bp)

    # Register dashboard and unit API blueprints
    from .blueprints.api.dashboard_routes import dashboard_api_bp  # Import dashboard API blueprint
    from .blueprints.api.unit_routes import unit_api_bp  # Import unit API blueprint
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(unit_api_bp)

    # Ensure all API routes are loaded
    with app.app_context():
        api_routes = [rule.rule for rule in app.url_map.iter_rules() if rule.rule.startswith('/api/')]
        print(f"Registered API routes: {api_routes}")

        # Check for specific container route
        container_routes = [rule.rule for rule in app.url_map.iter_rules() if 'container' in rule.rule]
        print(f"Container routes found: {container_routes}")

        # Debug billing routes
        billing_routes = [rule.rule for rule in app.url_map.iter_rules() if 'billing' in rule.rule]
        print(f"Billing routes found: {billing_routes}")

        # Debug all registered endpoints
        all_endpoints = [(rule.rule, rule.endpoint) for rule in app.url_map.iter_rules()]
        billing_endpoints = [ep for ep in all_endpoints if 'billing' in ep[1]]
        print(f"Billing endpoints: {billing_endpoints}")

    # Load additional config if provided
    #if config_filename:
    #    app.config.from_pyfile(config_filename)

    # Import models to ensure they're registered
    from . import models
    from .models import Unit, IngredientCategory

    # Setup logging
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    # Enable debug logging in development
    if app.debug:
        import logging
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.DEBUG)

    # Initialize API routes
    try:
        from .blueprints.api import init_api
        init_api(app)
    except ImportError:
        pass

    # Register template filters
    from .utils.template_filters import register_filters
    register_filters(app)

    # Register filters
    from .filters.product_filters import register_filters
    register_filters(app)

    # Using standard Flask url_for - no custom template registry needed

    # Add custom template filters
    @app.template_filter('attr_multiply')
    def attr_multiply_filter(item, attr1, attr2):
        """Multiply two attributes of a single item"""
        if item is None:
            return 0
        val1 = getattr(item, attr1, 0)
        val2 = getattr(item, attr2, 0)
        if val1 is None:
            val1 = 0
        if val2 is None:
            val2 = 0
        return float(val1) * float(val2)

    # Context processors
    @app.context_processor
    def inject_units():
        units = Unit.query.order_by(Unit.type, Unit.name).all()
        categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        return dict(units=units, categories=categories)

    @app.context_processor
    def inject_permissions():
        from .utils.permissions import has_permission, has_role, is_organization_owner
        from .services.reservation_service import ReservationService

        def get_reservation_summary(inventory_item_id):
            """Get reservation summary for template use"""
            from .models import ProductSKU
            sku = ProductSKU.query.filter_by(inventory_item_id=inventory_item_id).first()
            if sku:
                return ReservationService.get_reservation_summary_for_sku(sku)
            return {'available': 0.0, 'reserved': 0.0, 'total': 0.0, 'reservations': []}

        return dict(
            has_permission=has_permission,
            has_role=has_role,
            is_organization_owner=is_organization_owner,
            get_reservation_summary=get_reservation_summary
        )

    # Add main routes
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                return redirect(url_for('app_routes.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

    # Seeders are available via CLI commands: flask seed-all, flask init-db
    # No automatic seeding on startup to improve performance

    # Register template globals for permissions
    from .utils.permissions import has_permission, has_role, has_subscription_feature, is_organization_owner, is_developer, get_effective_organization_id

    def template_has_permission(permission_name):
        """Template helper for permission checking"""
        try:
            return has_permission(permission_name)
        except Exception as e:
            print(f"Permission check error for {permission_name}: {e}")
            return False

    def template_has_role(role_name):
        """Template helper for role checking"""
        try:
            return has_role(role_name)
        except Exception as e:
            print(f"Role check error for {role_name}: {e}")
            return False

    def template_is_org_owner():
        """Template helper for organization owner check"""
        try:
            return is_organization_owner()
        except Exception as e:
            print(f"Org owner check error: {e}")
            return False
    
    def template_can_access_route(route_path):
        """Template helper to check if user can access a route"""
        try:
            # This would check the route permissions mapping
            route_permissions = {
                '/inventory': 'inventory.view',
                '/recipes': 'recipes.view', 
                '/batches': 'batches.view',
                '/products': 'products.view',
                '/timers': 'timers.view',
                '/organization': 'organization.view',
            }
            
            for route_prefix, required_permission in route_permissions.items():
                if route_path.startswith(route_prefix):
                    return has_permission(required_permission)
            return True  # No specific permission required
        except Exception as e:
            print(f"Route access check error for {route_path}: {e}")
            return False

    def template_get_org_id():
        """Template helper to get effective organization ID"""
        try:
            return get_effective_organization_id()
        except Exception as e:
            print(f"Organization ID check error: {e}")
            return None

    app.jinja_env.globals['has_permission'] = template_has_permission
    app.jinja_env.globals['has_role'] = template_has_role
    app.jinja_env.globals['has_subscription_feature'] = has_subscription_feature
    app.jinja_env.globals['is_organization_owner'] = template_is_org_owner
    app.jinja_env.globals['is_developer'] = is_developer
    app.jinja_env.globals['can_access_route'] = template_can_access_route
    app.jinja_env.globals['get_effective_org_id'] = template_get_org_id

    # Add units to global context for dropdowns
    @app.context_processor
    def inject_units():
        from .models import Unit
        try:
            # Get all units, filtering by is_active if the column exists
            units = Unit.query.filter(
                db.or_(Unit.is_active == True, Unit.is_active.is_(None))
            ).order_by(Unit.type, Unit.name).all()
            return dict(global_units=units)
        except:
            # Fallback to all units if filtering fails
            try:
                units = Unit.query.order_by(Unit.type, Unit.name).all()
                return dict(global_units=units)
            except:
                return dict(global_units=[])

    # Register Jinja2 filters
    from .filters.product_filters import product_variant_name, ingredient_cost_currency, safe_float
    app.jinja_env.filters['product_variant_name'] = product_variant_name
    app.jinja_env.filters['ingredient_cost_currency'] = ingredient_cost_currency
    app.jinja_env.filters['safe_float'] = safe_float

    # Add timezone utilities to template context
    from .utils.timezone_utils import TimezoneUtils
    app.jinja_env.globals['TimezoneUtils'] = TimezoneUtils
    app.jinja_env.globals['current_time'] = TimezoneUtils.utc_now

    from .management import register_commands
    register_commands(app)

    # Force HTTPS redirect in production
    @app.before_request
    def force_https():
        if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
            # Check if the request is not secure and not already HTTPS
            if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
                # Only redirect if we're not already on an HTTPS URL
                if request.url.startswith('http://'):
                    return redirect(request.url.replace('http://', 'https://'), code=301)

    # Add security headers for HTTPS
    @app.after_request
    def add_security_headers(response):
        if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    return app