import os
import logging
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user
from sqlalchemy.pool import StaticPool
from datetime import timedelta

# Import extensions and new modules
from .extensions import db, migrate, csrf, limiter
from .authz import configure_login_manager
from .middleware import register_middleware
from .template_context import register_template_context
from .blueprints_registry import register_blueprints
from .utils.template_filters import register_template_filters
from .logging_config import configure_logging

logger = logging.getLogger(__name__)

def create_app(config=None):
    """Create and configure Flask application"""
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # Load configuration
    app.config.from_object("app.config.Config")
    if config:
        app.config.update(config)

    # Testing configuration
    if app.config.get('TESTING'):
        # Keep CSRF disabled for form tests, but allow login security to function
        app.config.setdefault("WTF_CSRF_ENABLED", False)

    # Tests pass DATABASE_URL; SQLAlchemy wants SQLALCHEMY_DATABASE_URI
    if config and "DATABASE_URL" in config:
        app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]

    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    os.makedirs('static/product_images', exist_ok=True)

    # Production security settings
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        app.config.update({
            'PREFERRED_URL_SCHEME': 'https',
            'SESSION_COOKIE_SECURE': True,
            'SESSION_COOKIE_HTTPONLY': True,
            'PERMANENT_SESSION_LIFETIME': 1800,
            'SESSION_COOKIE_SAMESITE': 'Lax'
        })

    # SQLite engine options for tests/memory databases
    _configure_sqlite_engine_options(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    configure_login_manager(app)

    # Initialize session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=31)

    # Clear all dismissed alerts on app restart - Flask 2.2+ compatible
    with app.app_context():
        # Sessions will be cleared automatically on app restart since we're using the default session interface
        pass

    # Register application components
    register_middleware(app)
    register_blueprints(app)
    register_template_context(app)
    register_template_filters(app)

    # Add core routes
    _add_core_routes(app)

    # Setup logging
    _setup_logging(app)

    # Configure logging
    configure_logging(app)

    # Register CLI commands
    from .management import register_commands
    register_commands(app)

    # Import models to ensure they're registered
    from . import models

    return app

def _configure_sqlite_engine_options(app):
    """Configure SQLite engine options for testing/memory databases"""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if app.config.get("TESTING") or uri.startswith("sqlite"):
        opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        # Remove pool args that SQLite memory + StaticPool don't accept
        opts.pop("pool_size", None)
        opts.pop("max_overflow", None)
        if uri == "sqlite:///:memory:":
            opts["poolclass"] = StaticPool
            opts["connect_args"] = {"check_same_thread": False}
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts

def _add_core_routes(app):
    """Add core application routes"""
    @app.route("/")
    def index():
        """Main landing page with proper routing logic"""
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))  # Developers go to developer dashboard
            else:
                return redirect(url_for('app_routes.dashboard'))  # Regular users go to user dashboard
        else:
            return render_template("homepage.html")  # Serve public homepage for unauthenticated users

    @app.route("/homepage")
    def homepage():
        """Public homepage - accessible to all users"""
        return render_template("homepage.html")

    @app.route("/public")
    def public_page():
        """Alternative public page"""
        return render_template("homepage.html")

def _setup_logging(app):
    """Setup application logging"""
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    if not app.debug and not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )

    if app.debug:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.DEBUG)