from flask import Flask, render_template, redirect, url_for
from flask_migrate import Migrate

def create_app(config_filename=None):
    app = Flask(__name__)
    app.config.from_pyfile(config_filename)

    from .models import db
    db.init_app(app)

    migrate = Migrate(app, db)

    from . import filters
    register_filters(app)

    # Add main routes
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('app_routes_bp.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

    return app