
import time
import functools
from flask import g, current_app
import logging

class PerformanceMonitor:
    @staticmethod
    def monitor_db_queries():
        """Track database query performance"""
        if not hasattr(g, 'query_count'):
            g.query_count = 0
            g.query_time = 0
    
    @staticmethod
    def log_slow_queries(duration_threshold=0.1):
        """Log queries that exceed threshold"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration > duration_threshold:
                    current_app.logger.warning(
                        f"Slow query in {func.__name__}: {duration:.3f}s"
                    )
                
                return result
            return wrapper
        return decorator

def profile_route(func):
    """Profile route performance"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        result = func(*args, **kwargs)
        
        duration = time.time() - start_time
        if duration > 1.0:  # Log routes taking > 1 second
            current_app.logger.warning(
                f"Slow route {func.__name__}: {duration:.3f}s"
            )
        
        return result
    return wrapper
