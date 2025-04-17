from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///batchtrack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/product_images'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Import db instance and models
from models import db, User, Recipe, InventoryItem, InventoryUnit

# Initialize db with app
db.init_app(app)
migrate = Migrate(app, db)

# Setup LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Register all blueprints
from routes.batch_routes import batches_bp
from routes.admin_routes import admin_bp
from routes.inventory_routes import inventory_bp
from routes.recipe_routes import recipes_bp
from routes.bulk_stock_routes import bulk_stock_bp
from routes.inventory_adjust_routes import adjust_bp
from routes.products import products_bp # Added import for products blueprint

from routes.fault_log_routes import faults_bp
from routes.product_log_routes import product_log_bp
from routes.tag_manager_routes import tag_bp
from routes.product_routes import product_bp
from blueprints.quick_add.routes import quick_add_bp

# Register blueprints
app.register_blueprint(quick_add_bp, url_prefix='/quick-add')
app.register_blueprint(product_bp)
from routes.app_routes import app_routes_bp
app.register_blueprint(app_routes_bp)  # No prefix since it handles root route
app.register_blueprint(batches_bp, url_prefix='/batches')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(inventory_bp)  # No prefix to match /ingredients URLs
app.register_blueprint(recipes_bp, url_prefix='/recipes')
app.register_blueprint(bulk_stock_bp, url_prefix='/stock')
app.register_blueprint(adjust_bp, url_prefix='/adjust')

app.register_blueprint(faults_bp, url_prefix='/logs')
app.register_blueprint(product_log_bp, url_prefix='/products')
app.register_blueprint(tag_bp)  # No prefix to match /tags URLs
app.register_blueprint(products_bp, url_prefix='/products') #Added registration for products blueprint


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
            return redirect(url_for('home.homepage'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)