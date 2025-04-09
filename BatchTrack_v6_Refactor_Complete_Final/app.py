from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///batchtrack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/product_images'

# Import db instance from models
from models import db

# Initialize db with app
db.init_app(app)

# Import models after db initialization
from models import User
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Register blueprints
from admin_routes import admin_bp
from recipe_routes import recipes_bp
from batch_view_route import batch_view_bp
from fault_log_routes import faults_bp
from tag_manager_routes import tag_bp
from product_log_routes import product_log_bp
from inventory_adjust_routes import adjust_bp

app.register_blueprint(admin_bp)
app.register_blueprint(recipes_bp)
app.register_blueprint(batch_view_bp)
app.register_blueprint(faults_bp)
app.register_blueprint(tag_bp)
app.register_blueprint(product_log_bp)
app.register_blueprint(adjust_bp)

# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Base route
@app.route('/')
@login_required
def home():
    return render_template('homepage.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and u.check_password(request.form['password']):
            login_user(u)
            return redirect(url_for('home'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)