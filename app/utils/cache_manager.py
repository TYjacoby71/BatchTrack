import time
from threading import Lock


class SimpleCache:
    """Thread-safe in-memory cache with TTL and simple capacity eviction."""

    def __init__(self, max_size: int = 100, default_ttl: int = 300) -> None:
        self._cache = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() < entry["expires_at"]:
                return entry["value"]
            # expired; delete and miss
            del self._cache[key]
            return None

    def set(self, key, value, ttl: int | None = None):
        with self._lock:
            # Simple eviction: drop oldest item when at capacity
            if len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache)) if self._cache else None
                if oldest_key is not None:
                    del self._cache[oldest_key]

            expires_at = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = {"value": value, "expires_at": expires_at}

    def clear(self):
        with self._lock:
            self._cache.clear()


# Global cache instances for the app
conversion_cache = SimpleCache(max_size=200, default_ttl=3600)
drawer_request_cache = SimpleCache(max_size=100, default_ttl=30)

