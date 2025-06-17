
import os

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    
    # Database configuration
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.chmod(instance_path, 0o777)
    
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_path, 'new_batchtrack.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload configuration
    UPLOAD_FOLDER = 'static/product_images'
    
    # Ensure directories exist
    os.makedirs('static/product_images', exist_ok=True)

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Add production-specific settings here

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
