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

import multiprocessing
import os

def _env_int(key, default=None):
    """Get environment variable as integer with fallback"""
    try:
        return int(os.environ.get(key, default or 0))
    except (ValueError, TypeError):
        return default or 0

# Server socket
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 2048

# Worker processes
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")
workers = _env_int("GUNICORN_WORKERS", max(4, multiprocessing.cpu_count() * 2 + 1))
worker_connections = _env_int("GUNICORN_WORKER_CONNECTIONS", 1000)
max_requests = 1000
max_requests_jitter = 100

# Timeouts
timeout = _env_int("GUNICORN_TIMEOUT", 60)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = "batchtrack"

# Preload application
preload_app = True

# SSL (if needed)
if os.environ.get("GUNICORN_SSL_CERT"):
    certfile = os.environ.get("GUNICORN_SSL_CERT")
    keyfile = os.environ.get("GUNICORN_SSL_KEY")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)
