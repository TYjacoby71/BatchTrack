
import secrets
import hashlib
from flask import request, abort
from functools import wraps

class SecurityUtils:
    @staticmethod
    def rate_limit_check(key: str, limit: int = 100, window: int = 3600):
        """Simple in-memory rate limiting"""
        # In production, use Redis
        import time
        
        if not hasattr(SecurityUtils, '_rate_limits'):
            SecurityUtils._rate_limits = {}
        
        now = time.time()
        window_start = now - window
        
        # Clean old entries
        SecurityUtils._rate_limits = {
            k: v for k, v in SecurityUtils._rate_limits.items() 
            if v['last_request'] > window_start
        }
        
        if key not in SecurityUtils._rate_limits:
            SecurityUtils._rate_limits[key] = {'count': 1, 'last_request': now}
            return True
        
        entry = SecurityUtils._rate_limits[key]
        if entry['count'] >= limit:
            return False
        
        entry['count'] += 1
        entry['last_request'] = now
        return True
    
    @staticmethod
    def validate_csrf_token(token: str) -> bool:
        """Enhanced CSRF validation"""
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(token)
            return True
        except:
            return False

from functools import wraps

def rate_limit(limit: int = 100, per: int = 3600):
    """Rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            client_ip = request.remote_addr
            if not SecurityUtils.rate_limit_check(f"route_{func.__name__}_{client_ip}", limit, per):
                abort(429)  # Too Many Requests
            return func(*args, **kwargs)
        return wrapper
    return decorator
