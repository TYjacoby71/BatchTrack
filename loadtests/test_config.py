
import os
from app.config import DevelopmentConfig

class LoadTestConfig(DevelopmentConfig):
    """Configuration optimized for load testing"""
    
    # Relax rate limiting for load tests
    RATELIMIT_ENABLED = False
    
    # Disable CSRF for API testing
    WTF_CSRF_ENABLED = False
    
    # Reduce session timeout warnings
    PERMANENT_SESSION_LIFETIME_MINUTES = 60
    
    # Optimize database for concurrent connections
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 50,
        'max_overflow': 100,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': 30,
    }
    
    # Disable some debugging features that slow down responses
    SQLALCHEMY_RECORD_QUERIES = False
    DEBUG = False
