
from .routes import auth

def init_auth(app):
    app.register_blueprint(auth, url_prefix='/auth')
