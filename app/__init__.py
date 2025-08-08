from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from .extensions import db
from .models import User
import os
from flask_login import current_user
import logging # Import logging

# Set up a basic logger
logger = logging.getLogger(__name__) # Use logger instead of print for debug/error messages

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load configuration
    app.config.from_object('app.config.Config')

    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    os.makedirs('static/product_images', exist_ok=True)

    # Force HTTPS in production
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        app.config['PREFERRED_URL_SCHEME'] = 'https'
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Initialize extensions
    from .extensions import db, migrate, login_manager, mail, csrf
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # CSRF exempt will be applied directly to webhook routes in billing blueprint

    # Configure Flask-Login settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        try:
            user = db.session.get(User, int(user_id))
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
        from flask import request, abort, jsonify, session, redirect, url_for, g, flash
        from flask_login import current_user
        from app.utils.permissions import has_permission, get_effective_organization_id
        from app.models import Organization

        # Skip for static files, auth routes, and webhooks
        if (request.path.startswith('/static/') or
            request.path.startswith('/auth/login') or
            request.path.startswith('/auth/logout') or
            request.path.startswith('/auth/signup') or
            request.path.startswith('/billing/webhooks/') or
            request.path == '/' or
            request.path == '/homepage'):
            return None

        # Require authentication for all other routes
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

        # Developer customer view - make them work exactly like organization owners
        if current_user.user_type == 'developer':
            # Allow developer-only routes
            if request.path.startswith('/developer/'):
                return None
            # Allow auth routes
            if request.path.startswith('/auth/'):
                return None

            # For all customer routes, require organization selection and inject organization context
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                if request.is_json:
                    return jsonify({'error': 'Developer must select organization to access customer features'}), 403
                flash('Please select an organization to access customer features', 'warning')
                return redirect(url_for('developer.organizations'))

            # CRITICAL: Temporarily inject organization context for developers
            # This makes them work exactly like organization owners for the selected org
            selected_org = Organization.query.get(selected_org_id)
            if not selected_org:
                session.pop('dev_selected_org_id', None)
                flash('Selected organization no longer exists', 'error')
                return redirect(url_for('developer.organizations'))

            # Store effective organization context in Flask g for developer masquerade
            g.effective_org_id = selected_org_id
            g.effective_org = selected_org
            g.is_developer_masquerade = True

        # Organization scoping enforcement for regular users
        elif not current_user.organization_id:
            if request.is_json:
                return jsonify({'error': 'No organization context'}), 403
            flash('No organization context available', 'error')
            return redirect(url_for('auth.logout'))

        # Permission checking is now handled by route decorators
        # This middleware only handles organization scoping
        return None

    # Register blueprints with URL prefixes
    try:
        from .blueprints.auth.routes import auth_bp
        from .blueprints.inventory.routes import inventory_bp
        from .blueprints.recipes.routes import recipes_bp
        from .blueprints.batches.routes import batches_bp
        from .blueprints.batches.finish_batch import finish_batch_bp
        from .blueprints.batches.start_batch import start_batch_bp
        from .blueprints.batches.cancel_batch import cancel_batch_bp
        from .blueprints.api.routes import api_bp
        from .blueprints.settings.routes import settings_bp
        from .blueprints.expiration.routes import expiration_bp
        from .blueprints.conversion.routes import conversion_bp
        from .blueprints.organization.routes import organization_bp
        from .blueprints.billing.routes import billing_bp
        from .blueprints.developer.routes import developer_bp
        from .blueprints.timers.routes import timers_bp
        from .routes.app_routes import app_routes_bp
        from .blueprints.fifo import fifo_bp
        from .blueprints.batches.add_extra import add_extra_bp
        from .routes import bulk_stock_routes
        from .routes import fault_log_routes
        from .routes import tag_manager_routes

        # Register admin blueprints
        from .blueprints.admin.admin_routes import admin_bp
        app.register_blueprint(admin_bp)

        # Register API blueprints
        from .blueprints.api.stock_routes import stock_api_bp
        from .blueprints.api.ingredient_routes import ingredient_api_bp
        from .blueprints.api.container_routes import container_api_bp

    except ImportError as e:
        logger.warning(f"Failed to import some blueprints: {e}")

    # Register reservation blueprints (now under products)
    try:
        from .blueprints.products.reservation_routes import reservation_bp
        from .blueprints.api.reservation_routes import reservation_api_bp
        app.register_blueprint(reservation_bp, url_prefix='/reservations')
        app.register_blueprint(reservation_api_bp)
    except ImportError:
        logger.warning("Could not register reservation blueprints")

    # Register all blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(finish_batch_bp, url_prefix='/batches')
    app.register_blueprint(cancel_batch_bp, url_prefix='/batches')
    app.register_blueprint(start_batch_bp, url_prefix='/start-batch')
    app.register_blueprint(developer_bp)
    
    # Register billing blueprint
    try:
        app.register_blueprint(billing_bp)
        logger.debug(f"Billing blueprint registered successfully")

        # Debug billing routes
        billing_routes = [rule.rule for rule in app.url_map.iter_rules() if rule.endpoint and rule.endpoint.startswith('billing.')]
        logger.debug(f"Billing routes registered: {billing_routes}")
    except Exception as e:
        logger.error(f"Failed to register billing blueprint: {e}")
        # Continue without billing blueprint for now
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
        logger.warning("Could not register any product blueprints")
        pass

    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(expiration_bp, url_prefix='/expiration')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(app_routes_bp)
    app.register_blueprint(fifo_bp)
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')
    app.register_blueprint(bulk_stock_routes.bulk_stock_bp, url_prefix='/bulk_stock')
    app.register_blueprint(fault_log_routes.fault_log_bp, url_prefix='/fault_log')
    app.register_blueprint(tag_manager_routes.tag_manager_bp, url_prefix='/tag_manager')
    app.register_blueprint(organization_bp, url_prefix='/organization')
    app.register_blueprint(api_bp)

    # Register dashboard and unit API blueprints
    from .blueprints.api.dashboard_routes import dashboard_api_bp  # Import dashboard API blueprint
    from .blueprints.api.unit_routes import unit_api_bp  # Import unit API blueprint
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(ingredient_api_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(unit_api_bp)
    app.register_blueprint(container_api_bp)


    # Ensure all API routes are loaded
    with app.app_context():
        if app.debug:
            api_routes = [rule.rule for rule in app.url_map.iter_rules() if rule.rule.startswith('/api/')]
            logger.debug(f"Registered API routes: {api_routes}")

            # Check for specific container route
            container_routes = [rule.rule for rule in app.url_map.iter_rules() if 'container' in rule.rule]
            logger.debug(f"Container routes found: {container_routes}")

            # Debug billing routes
            billing_routes = [rule.rule for rule in app.url_map.iter_rules() if 'billing' in rule.rule]
            logger.debug(f"Billing routes found: {billing_routes}")

            # Debug all registered endpoints
            all_endpoints = [(rule.rule, rule.endpoint) for rule in app.url_map.iter_rules()]
            billing_endpoints = [ep for ep in all_endpoints if ep[1] and 'billing' in ep[1]]
            logger.debug(f"Billing endpoints: {billing_endpoints}")

    # Load additional config if provided
    #if config_filename:
    #    app.config.from_pyfile(config_filename)

    # Import models to ensure they're registered
    from . import models
    from .models import Unit, IngredientCategory

    # Setup logging
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    # Configure basic logging for production
    if not app.debug and not logger.handlers:
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

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
        try:
            # Get all units, filtering by is_active if the column exists
            units = Unit.query.filter(
                db.or_(Unit.is_active == True, Unit.is_active.is_(None))
            ).order_by(Unit.unit_type, Unit.name).all()
        except:
            # Fallback to all units if filtering fails
            try:
                units = Unit.query.order_by(Unit.unit_type, Unit.name).all()
            except:
                units = []

        try:
            categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        except:
            categories = []

        return dict(units=units, categories=categories, global_units=units)

    @app.context_processor
    def inject_permissions():
        from .utils.permissions import has_permission, has_role, is_organization_owner
        from .services.reservation_service import ReservationService
        from .utils.unit_utils import get_global_unit_list

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
            get_reservation_summary=get_reservation_summary,
            get_global_unit_list=get_global_unit_list
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
            # Always call with just permission name from templates
            return has_permission(permission_name)
        except Exception as e:
            logger.error(f"Permission check error for {permission_name}: {e}")
            return False

    def template_has_role(role_name):
        """Template helper for role checking"""
        try:
            return has_role(role_name)
        except Exception as e:
            logger.error(f"Role check error for {role_name}: {e}")
            return False

    def template_is_org_owner():
        """Template helper for organization owner check"""
        try:
            return is_organization_owner()
        except Exception as e:
            logger.error(f"Org owner check error: {e}")
            return False

    def template_can_access_route(route_path):
        """Template helper to check if user can access a route"""
        try:
            # Route permissions are now handled by decorators
            # This helper is deprecated but maintained for backward compatibility
            return True
        except Exception as e:
            logger.error(f"Route access check error for {route_path}: {e}")
            return False

    def template_get_org_id():
        """Template helper to get effective organization ID"""
        try:
            return get_effective_organization_id()
        except Exception as e:
            logger.error(f"Organization ID check error: {e}")
            return None

    app.jinja_env.globals['has_permission'] = template_has_permission
    app.jinja_env.globals['has_role'] = template_has_role
    app.jinja_env.globals['has_subscription_feature'] = has_subscription_feature
    app.jinja_env.globals['is_organization_owner'] = template_is_org_owner
    app.jinja_env.globals['is_developer'] = is_developer
    app.jinja_env.globals['can_access_route'] = template_can_access_route
    app.jinja_env.globals['get_effective_org_id'] = template_get_org_id



    # Register Jinja2 filters
    from .filters.product_filters import product_variant_name, ingredient_cost_currency, safe_float
    app.jinja_env.filters['product_variant_name'] = product_variant_name
    app.jinja_env.filters['ingredient_cost_currency'] = ingredient_cost_currency
    app.jinja_env.filters['safe_float'] = safe_float

    # Add timezone utilities to template context
    from .utils.timezone_utils import TimezoneUtils
    app.jinja_env.globals['TimezoneUtils'] = TimezoneUtils
    app.jinja_env.globals['current_time'] = TimezoneUtils.utc_now

    # Make TimezoneUtils available in templates
    @app.context_processor
    def inject_timezone_utils():
        return dict(TimezoneUtils_global=TimezoneUtils)

    # Make get_organization_by_id available in templates
    @app.context_processor
    def inject_organization_helpers():
        from .models import Organization
        from .utils.permissions import get_effective_organization_id
        
        def get_organization_by_id(org_id):
            if org_id:
                try:
                    return db.session.get(Organization, org_id)
                except:
                    return Organization.query.get(org_id)  # Fallback for older SQLAlchemy
            return None
            
        def get_current_organization():
            """Get the current organization context (works with developer masquerade)"""
            org_id = get_effective_organization_id()
            return get_organization_by_id(org_id) if org_id else None
            
        return dict(
            get_organization_by_id=get_organization_by_id,
            get_current_organization=get_current_organization
        )

    from .management import register_commands
    register_commands(app)

    # Force HTTPS redirect in production
    @app.before_request
    def force_https():
        from flask import request, redirect
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

    # Register error handlers
    # Register error handlers

    # Register billing access middleware
    @app.before_request
    def enforce_billing_access():
        """Global middleware to enforce billing access control"""
        from flask import request, session, redirect, url_for, flash
        from flask_login import current_user

        # Skip for static files, auth routes, and billing routes
        if (request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint.startswith('auth.') or
            request.endpoint.startswith('billing.')
        )):
            return

        # Only check authenticated users with organizations
        if current_user.is_authenticated and current_user.organization:
            # Check organization access authorization using the new authorization system
            from .utils.authorization import AuthorizationHierarchy
            has_access, reason = AuthorizationHierarchy.check_organization_access(current_user.organization)
            if not has_access:
                if reason == 'organization_suspended':
                    flash('Your organization has been suspended. Please contact support.', 'error')
                    return redirect(url_for('billing.upgrade'))
                elif reason not in ['exempt', 'developer']:
                    flash('Subscription required to access the system.', 'error')
                    return redirect(url_for('billing.upgrade'))

    return app