"""Production-ready Gunicorn defaults for BatchTrack.

These values are tuned for high concurrency with cooperative workers. Override
them via environment variables as needed (see variables below). Bind to the
same interface/port expected by your load balancer or ingress.
"""

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")

# Cooperative workers give us better concurrency per CPU for IO-bound Flask apps
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")
workers = _env_int("GUNICORN_WORKERS", max(4, multiprocessing.cpu_count() * 2 + 1))
worker_connections = _env_int("GUNICORN_WORKER_CONNECTIONS", 1000)

timeout = _env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)

# Automatically recycle workers to mitigate memory bloat
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)

# Logging
accesslog = os.environ.get("GUNICORN_ACCESSLOG", "-")
errorlog = os.environ.get("GUNICORN_ERRORLOG", "-")
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")

