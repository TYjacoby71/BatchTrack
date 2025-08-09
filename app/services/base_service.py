
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from flask import current_app
import logging

class BaseService(ABC):
    """Base service class providing common functionality"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def log_operation(self, operation: str, data: Dict[str, Any], user_id: Optional[int] = None):
        """Centralized operation logging"""
        self.logger.info(f"Operation: {operation}", extra={
            'operation': operation,
            'data': data,
            'user_id': user_id,
            'service': self.__class__.__name__
        })
    
    def validate_organization_access(self, organization_id: int, user_id: int) -> bool:
        """Centralized organization access validation"""
        from flask_login import current_user
        
        if current_user.user_type == 'developer':
            return True
            
        return current_user.organization_id == organization_id
    
    def handle_service_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Centralized error handling"""
        self.logger.error(f"Service error in {operation}: {str(error)}")
        return {
            'success': False,
            'error': str(error),
            'operation': operation
        }

class CacheableService(BaseService):
    """Service with caching capabilities"""
    
    def __init__(self):
        super().__init__()
        self._cache = {}
    
    def get_cached(self, key: str, fetch_func, ttl: int = 300):
        """Simple in-memory caching with TTL"""
        import time
        
        if key in self._cache:
            cached_time, value = self._cache[key]
            if time.time() - cached_time < ttl:
                return value
        
        value = fetch_func()
        self._cache[key] = (time.time(), value)
        return value
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries"""
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
