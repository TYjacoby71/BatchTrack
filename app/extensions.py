from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_session import Session

# Initialize extensions
db = SQLAlchemy()
# Enable robust autogeneration and SQLite-friendly alters
migrate = Migrate(compare_type=True, render_as_batch=True)
csrf = CSRFProtect()
cache = Cache()
# Configure rate limiter with much higher limits for load testing
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10000 per day", "5000 per hour", "500 per minute"],
)
server_session = Session()

# Add Flask-Mail import with fallback
try:
    from flask_mail import Mail
    mail = Mail()
except ImportError:
    # Flask-Mail not installed - create a dummy object
    mail = None

# Configure login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from .models.models import User
    return db.session.get(User, int(user_id))