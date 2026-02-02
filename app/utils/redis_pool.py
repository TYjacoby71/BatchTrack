from __future__ import annotations

import logging
import os
from threading import Lock
from typing import Any

from flask import Flask, current_app, has_app_context

logger = logging.getLogger(__name__)

_POOL_INFO_KEY = "redis_pool_info"
_POOL_LOCK = Lock()
_STANDALONE_EXTENSIONS: dict[str, Any] = {}


def _float_setting(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_setting(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_setting(app: Flask | None, key: str) -> Any:
    if app is not None and key in app.config:
        return app.config.get(key)
    return os.environ.get(key)


def _resolve_pool_max_connections(app: Flask | None) -> int:
    explicit = _int_setting(_get_setting(app, "REDIS_POOL_MAX_CONNECTIONS"), None)
    if explicit is not None:
        return explicit

    redis_max = (
        _int_setting(_get_setting(app, "REDIS_MAX_CONNECTIONS"), None)
        or _int_setting(_get_setting(app, "REDIS_MAX_CLIENTS"), None)
    )
    if redis_max is not None:
        worker_count = (
            _int_setting(_get_setting(app, "WEB_CONCURRENCY"), None)
            or _int_setting(_get_setting(app, "GUNICORN_WORKERS"), None)
            or _int_setting(_get_setting(app, "WORKERS"), 1)
            or 1
        )
        worker_count = max(worker_count, 1)
        # Leave headroom for sidecars and administrative connections.
        return max(5, int(redis_max * 0.8 / worker_count))

    return 200


def _build_pool(app: Flask | None, redis_url: str):
    try:
        import redis
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("Redis library not installed; skipping shared connection pool setup.")
        return None, None, None

    max_conns = _resolve_pool_max_connections(app)
    pool_timeout = _float_setting(_get_setting(app, "REDIS_POOL_TIMEOUT"), 5.0)
    socket_timeout = _float_setting(_get_setting(app, "REDIS_SOCKET_TIMEOUT"), 5.0)
    connect_timeout = _float_setting(_get_setting(app, "REDIS_CONNECT_TIMEOUT"), 5.0)

    pool_class = getattr(redis, "BlockingConnectionPool", redis.ConnectionPool)
    pool = pool_class.from_url(
        redis_url,
        max_connections=None if max_conns <= 0 else max_conns,
        timeout=pool_timeout,
        socket_timeout=socket_timeout,
        socket_connect_timeout=connect_timeout,
    )
    return pool, max_conns, pool_timeout


def get_redis_pool(app: Flask | None = None):
    """Provision a Redis connection pool and refresh it after each worker fork."""
    if app is None and has_app_context():
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            app = None

    redis_url = None
    if app is not None:
        redis_url = app.config.get("REDIS_URL") or os.environ.get("REDIS_URL")
    else:
        redis_url = os.environ.get("REDIS_URL")

    if not redis_url:
        return None

    extensions = app.extensions if app is not None else _STANDALONE_EXTENSIONS
    current_pid = os.getpid()
    cached = extensions.get(_POOL_INFO_KEY)
    if cached and cached.get("pid") == current_pid:
        return cached.get("pool")

    with _POOL_LOCK:
        cached = extensions.get(_POOL_INFO_KEY)
        if cached:
            cached_pid = cached.get("pid")
            pool = cached.get("pool")
            if cached_pid == current_pid and pool is not None:
                return pool
            if pool is not None:
                try:
                    pool.disconnect()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Failed to disconnect inherited Redis pool (pid=%s): %s", cached_pid, exc)
            extensions.pop(_POOL_INFO_KEY, None)

    pool, max_conns, pool_timeout = _build_pool(app, redis_url)
    if pool is None:
        return None

    extensions[_POOL_INFO_KEY] = {"pid": current_pid, "pool": pool}
    if app is not None:
        app.extensions["redis_pool"] = pool  # backwards compatibility for any legacy access

    logger.info(
        "Initialized Redis connection pool (pid=%s, max_connections=%s, timeout=%ss)",
        current_pid,
        max_conns if max_conns and max_conns > 0 else "unbounded",
        pool_timeout,
    )
    return pool
