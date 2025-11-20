import logging
import time
import os
import pickle
from threading import Lock

try:
    import redis  # type: ignore
    from redis.exceptions import RedisError  # type: ignore
except Exception:  # optional dependency
    redis = None
    RedisError = Exception  # type: ignore[misc,assignment]


logger = logging.getLogger(__name__)


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

    def delete(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear_prefix(self, prefix: str):
        with self._lock:
            keys = [k for k in self._cache.keys() if str(k).startswith(prefix)]
            for k in keys:
                del self._cache[k]


class RedisCache:
    """Redis-backed cache with TTL and namespace scoping."""

    def __init__(self, namespace: str, default_ttl: int = 300, url: str | None = None) -> None:
        if redis is None:
            raise RuntimeError("redis package not available")
        self._namespace = namespace.strip(":")
        self._default_ttl = default_ttl
        self._client = redis.Redis.from_url(url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=False)
        self._fallback = SimpleCache(max_size=1000, default_ttl=default_ttl)
        self._redis_disabled_until = 0.0
        self._redis_backoff_seconds = 60

    def _k(self, key: str) -> str:
        return f"bt:{self._namespace}:{key}"

    def _can_use_redis(self) -> bool:
        return time.time() >= self._redis_disabled_until

    def _handle_redis_failure(self, action: str, exc: Exception) -> None:
        now = time.time()
        if now >= self._redis_disabled_until:
            logger.warning(
                "Redis cache %s failed (%s). Falling back to in-process cache for %ds",
                action,
                exc,
                self._redis_backoff_seconds,
            )
        self._redis_disabled_until = now + self._redis_backoff_seconds

    def get(self, key):
        if self._can_use_redis():
            try:
                raw = self._client.get(self._k(key))
                if raw is None:
                    self._fallback.delete(key)
                    return None
                value = pickle.loads(raw)
                self._fallback.set(key, value, ttl=self._default_ttl)
                return value
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("get", exc)
            except Exception:
                pass
        return self._fallback.get(key)

    def set(self, key, value, ttl: int | None = None):
        expires = ttl if ttl is not None else self._default_ttl
        if self._can_use_redis():
            try:
                raw = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                self._client.set(self._k(key), raw, ex=expires)
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("set", exc)
        self._fallback.set(key, value, ttl=expires)

    def delete(self, key):
        if self._can_use_redis():
            try:
                self._client.delete(self._k(key))
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("delete", exc)
        self._fallback.delete(key)

    def clear(self):
        self.clear_prefix("")

    def clear_prefix(self, prefix: str):
        if self._can_use_redis():
            try:
                match = f"bt:{self._namespace}:{prefix}*"
                cursor = 0
                pipe = self._client.pipeline()
                while True:
                    cursor, keys = self._client.scan(cursor=cursor, match=match, count=500)
                    if keys:
                        pipe.delete(*keys)
                    if cursor == 0:
                        break
                pipe.execute()
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("clear_prefix", exc)
        self._fallback.clear_prefix(prefix)


# Global cache instances for the app
USE_REDIS = bool(os.environ.get("REDIS_URL")) and redis is not None

if USE_REDIS:
    conversion_cache = RedisCache(namespace="conversion", default_ttl=3600)
    drawer_request_cache = RedisCache(namespace="drawer", default_ttl=30)
    app_cache = RedisCache(namespace="app", default_ttl=600)
else:
    conversion_cache = SimpleCache(max_size=200, default_ttl=3600)
    drawer_request_cache = SimpleCache(max_size=100, default_ttl=30)
    app_cache = SimpleCache(max_size=1000, default_ttl=600)

