from __future__ import annotations

import logging
import os
import pickle
import time
from threading import Lock
from typing import Any, Dict

from .redis_pool import get_redis_pool

try:  # optional dependency
    import redis  # type: ignore
    from redis.exceptions import RedisError  # type: ignore
except Exception:  # pragma: no cover - optional dependency missing
    redis = None
    RedisError = Exception  # type: ignore[misc,assignment]


__all__ = [
    "SimpleCache",
    "RedisCache",
    "conversion_cache",
    "drawer_request_cache",
    "app_cache",
]

logger = logging.getLogger(__name__)


class SimpleCache:
    """Thread-safe in-memory cache with TTL and simple capacity eviction."""

    def __init__(self, max_size: int = 100, default_ttl: int = 300) -> None:
        self._cache: Dict[Any, Dict[str, Any]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = Lock()

    def get(self, key: Any) -> Any:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() < entry["expires_at"]:
                return entry["value"]
            del self._cache[key]
            return None

    def set(self, key: Any, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache)) if self._cache else None
                if oldest_key is not None:
                    del self._cache[oldest_key]

            expires_at = time.time() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = {"value": value, "expires_at": expires_at}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def delete(self, key: Any) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear_prefix(self, prefix: str) -> None:
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
        self._url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        self._pool = None
        self._fallback = SimpleCache(max_size=1000, default_ttl=default_ttl)
        self._redis_disabled_until = 0.0
        self._redis_backoff_seconds = 60

    def _k(self, key: str) -> str:
        return f"bt:{self._namespace}:{key}"

    def _get_client(self):
        if redis is None:
            raise RuntimeError("redis package not available")

        pool = get_redis_pool()
        if pool is not None and pool is not self._pool:
            self._pool = pool
            self._client = redis.Redis(connection_pool=pool, decode_responses=False)
            return self._client

        if self._client is None:
            if pool is None:
                self._client = redis.Redis.from_url(self._url, decode_responses=False)
            else:
                self._pool = pool
                self._client = redis.Redis(connection_pool=pool, decode_responses=False)

        return self._client

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

    def get(self, key: str) -> Any:
        if self._can_use_redis():
            try:
                client = self._get_client()
                raw = client.get(self._k(key))
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

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires = ttl if ttl is not None else self._default_ttl
        if self._can_use_redis():
            try:
                client = self._get_client()
                raw = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                client.set(self._k(key), raw, ex=expires)
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("set", exc)
        self._fallback.set(key, value, ttl=expires)

    def delete(self, key: str) -> None:
        if self._can_use_redis():
            try:
                client = self._get_client()
                client.delete(self._k(key))
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("delete", exc)
        self._fallback.delete(key)

    def clear(self) -> None:
        self.clear_prefix("")

    def clear_prefix(self, prefix: str) -> None:
        if self._can_use_redis():
            try:
                client = self._get_client()
                match = f"bt:{self._namespace}:{prefix}*"
                cursor = 0
                pipe = client.pipeline()
                while True:
                    cursor, keys = client.scan(cursor=cursor, match=match, count=500)
                    if keys:
                        pipe.delete(*keys)
                    if cursor == 0:
                        break
                pipe.execute()
            except RedisError as exc:  # type: ignore[arg-type]
                self._handle_redis_failure("clear_prefix", exc)
        self._fallback.clear_prefix(prefix)


USE_REDIS = bool(os.environ.get("REDIS_URL")) and redis is not None

if USE_REDIS:
    conversion_cache = RedisCache(namespace="conversion", default_ttl=3600)
    drawer_request_cache = RedisCache(namespace="drawer", default_ttl=30)
    app_cache = RedisCache(namespace="app", default_ttl=600)
else:
    conversion_cache = SimpleCache(max_size=200, default_ttl=3600)
    drawer_request_cache = SimpleCache(max_size=100, default_ttl=30)
    app_cache = SimpleCache(max_size=1000, default_ttl=600)