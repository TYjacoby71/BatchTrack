
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os

# Create the db object first
db = SQLAlchemy()

# Create app and attach config
app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'
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

# Import models after db initialization
from models import User, Recipe, InventoryItem, Unit, IngredientCategory

# Setup logging
from utils.unit_utils import setup_logging
setup_logging(app)

# Setup LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Register all blueprints
from routes.batch_routes import batches_bp
from blueprints.inventory.routes import inventory_bp
from blueprints.recipes.routes import recipes_bp
from blueprints.conversion.routes import conversion_bp
from blueprints.settings.routes import settings_bp
from blueprints.quick_add.routes import quick_add_bp
from routes.bulk_stock_routes import bulk_stock_bp
from routes.inventory_adjust_routes import adjust_bp
from routes.products import products_bp
from routes.fault_log_routes import faults_bp
from routes.product_log_routes import product_log_bp
from routes.tag_manager_routes import tag_bp
from routes.product_routes import product_bp
from blueprints.quick_add.routes import quick_add_bp
from routes.timer_routes import timers_bp
from blueprints.settings.routes import settings_bp
from blueprints.conversion.routes import conversion_bp

# Register blueprints
from routes.admin_routes import admin_bp
app.register_blueprint(conversion_bp, url_prefix='/conversion')
app.register_blueprint(quick_add_bp, url_prefix='/quick-add')
app.register_blueprint(product_bp)
app.register_blueprint(settings_bp, url_prefix='/settings')
from routes.app_routes import app_routes_bp
app.register_blueprint(app_routes_bp)
app.register_blueprint(batches_bp, url_prefix='/batches')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(inventory_bp, url_prefix='/inventory')
app.register_blueprint(recipes_bp, url_prefix='/recipes')
app.register_blueprint(bulk_stock_bp, url_prefix='/stock')
app.register_blueprint(adjust_bp, url_prefix='/adjust')
app.register_blueprint(faults_bp, url_prefix='/logs')
app.register_blueprint(product_log_bp, url_prefix='/product-logs')
app.register_blueprint(tag_bp, url_prefix='/tags')
app.register_blueprint(products_bp, url_prefix='/products')
app.register_blueprint(timers_bp, url_prefix='/timers')

@app.context_processor
def inject_units():
    units = Unit.query.order_by(Unit.type, Unit.name).all()
    categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
    return dict(units=units, categories=categories)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('login.html')

        u = User.query.filter_by(username=username).first()
        if u and u.check_password(password):
            login_user(u)
            return redirect(url_for('dashboard.dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard.dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
