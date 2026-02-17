import logging
from abc import ABC
from typing import Any, Dict, Optional

from app.utils.cache_manager import app_cache


class BaseService(ABC):
    """Base service class providing common functionality"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def log_operation(
        self, operation: str, data: Dict[str, Any], user_id: Optional[int] = None
    ):
        """Centralized operation logging"""
        self.logger.info(
            f"Operation: {operation}",
            extra={
                "operation": operation,
                "data": data,
                "user_id": user_id,
                "service": self.__class__.__name__,
            },
        )

    def validate_organization_access(self, organization_id: int, user_id: int) -> bool:
        """Centralized organization access validation"""
        from flask_login import current_user

        if current_user.user_type == "developer":
            return True

        return current_user.organization_id == organization_id

    def handle_service_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """Centralized error handling"""
        self.logger.error(f"Service error in {operation}: {str(error)}")
        return {"success": False, "error": str(error), "operation": operation}


class CacheableService(BaseService):
    """Service with caching capabilities"""

    def __init__(self):
        super().__init__()

    def get_cached(self, key: str, fetch_func, ttl: int = 300):
        """Centralized in-memory caching with TTL using app_cache."""
        namespaced_key = f"{self.__class__.__name__}:{key}"
        cached = app_cache.get(namespaced_key)
        if cached is not None:
            return cached
        value = fetch_func()
        app_cache.set(namespaced_key, value, ttl=ttl)
        return value

    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries for this service from centralized cache."""
        prefix = f"{self.__class__.__name__}:"
        if pattern:
            app_cache.clear_prefix(prefix + pattern)
        else:
            app_cache.clear_prefix(prefix)
