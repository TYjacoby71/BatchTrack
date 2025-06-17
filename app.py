from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
import os

# Create the db object first
db = SQLAlchemy()

# Create app and attach config
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.add_url_rule('/data/<path:filename>', endpoint='data', view_func=app.send_static_file)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
# Ensure directories exist with proper permissions
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)
os.makedirs('static/product_images', exist_ok=True)
os.chmod(instance_path, 0o777)  # Ensure write permissions

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'new_batchtrack.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/product_images'

# Initialize db with app
db.init_app(app)
migrate = Migrate(app, db)

csrf = CSRFProtect()
csrf.init_app(app)

# Setup logging
from utils.unit_utils import setup_logging
setup_logging(app)

# Setup LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Import and register blueprints
from blueprints.batches.start_batch import start_batch_bp
from blueprints.batches.finish_batch import finish_batch_bp
from blueprints.batches.cancel_batch import cancel_batch_bp
from blueprints.batches.add_extra import add_extra_bp
from blueprints.batches.routes import batches_bp
from blueprints.inventory.routes import inventory_bp
from blueprints.recipes.routes import recipes_bp
from blueprints.conversion.routes import conversion_bp
from blueprints.settings.routes import settings_bp
from blueprints.quick_add.routes import quick_add_bp
from routes.bulk_stock_routes import bulk_stock_bp
# Inventory adjustments now handled in blueprints/inventory/routes.py
from routes.fault_log_routes import faults_bp
from routes.product_log_routes import product_log_bp
from routes.tag_manager_routes import tag_bp
from routes.products import products_bp
from routes.product_variants import product_variants_bp
from routes.product_inventory import product_inventory_bp
from routes.product_api import product_api_bp
from filters.product_filters import register_product_filters
from blueprints.fifo import fifo_bp
from blueprints.expiration.routes import expiration_bp
from routes.admin_routes import admin_bp
from routes.app_routes import app_routes_bp
from blueprints.api import init_api
from blueprints.timers import timers_bp

# Register blueprints
from routes.app_routes import app_routes_bp
from routes.admin_routes import admin_bp
from routes.products import products_bp
from routes.product_api import product_api_bp
from routes.product_inventory import product_inventory_bp
from routes.product_log_routes import product_log_bp
from routes.fault_log_routes import faults_bp
from routes.tag_manager_routes import tag_bp
from routes.bulk_stock_routes import bulk_stock_bp
from routes.product_variants import product_variants_bp
from routes.email_signup_routes import email_signup_bp

app.register_blueprint(app_routes_bp)
app.register_blueprint(batches_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(recipes_bp)
app.register_blueprint(conversion_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(quick_add_bp)
app.register_blueprint(expiration_bp)
app.register_blueprint(fifo_bp)
app.register_blueprint(timers_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(products_bp)
app.register_blueprint(product_api_bp)
app.register_blueprint(product_inventory_bp)
app.register_blueprint(product_log_bp)
app.register_blueprint(faults_bp)
app.register_blueprint(tag_bp)
app.register_blueprint(bulk_stock_bp)
app.register_blueprint(product_variants_bp)
app.register_blueprint(email_signup_bp)

# Initialize API routes
init_api(app)

# Register product filters
register_product_filters(app)

# Add custom Jinja2 filter for cost calculations
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

@app.context_processor
def inject_units():
    from models import Unit, IngredientCategory
    units = Unit.query.order_by(Unit.type, Unit.name).all()
    categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
    return dict(units=units, categories=categories)

@app.context_processor
def inject_permissions():
    from utils.permissions import has_permission, has_role
    return dict(has_permission=has_permission, has_role=has_role)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    from flask_wtf import FlaskForm
    from werkzeug.security import generate_password_hash
    from models import User

    form = FlaskForm()
    if request.method == 'POST' and form.validate_on_submit():
        form_type = request.form.get('form_type')
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('login.html', form=form)

        if form_type == 'register':
            # Handle registration
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                flash('Passwords do not match')
                return render_template('login.html', form=form)

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists')
                return render_template('login.html', form=form)

            # Create new user
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()

            flash('Account created successfully! Please log in.')
            return render_template('login.html', form=form)

        else:
            # Handle login
            u = User.query.filter_by(username=username).first()
            if u and u.check_password(password):
                login_user(u)
                return redirect(url_for('dashboard.dashboard'))
            flash('Invalid credentials')

    return render_template('login.html', form=form)

@app.route('/dev-login')
def dev_login():
    # Placeholder for future dev login page
    flash('Developer login coming soon!')
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return render_template("homepage.html")

@app.route('/homepage')
def homepage():
    return render_template('homepage.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)