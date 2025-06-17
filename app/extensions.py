
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def init_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # LoginManager configuration
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, redirect, url_for
        # Allow access to homepage and login routes without authentication
        if request.endpoint in ['homepage', 'index', 'auth.login', 'auth.dev_login'] or request.path in ['/', '/homepage', '/login']:
            return None  # Let the route handle it normally
        return redirect(url_for('auth.login', next=request.url))
