
import multiprocessing
import os

# Gunicorn configuration for high-concurrency production deployment
# Optimized for 10k+ concurrent users


def _env_int(key, default):
    """Helper to parse environment integers with fallback."""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _configured_workers():
    cpu_count = max(multiprocessing.cpu_count(), 1)
    # Keep defaults conservative so small instances don't overcommit memory.
    default_workers = max(1, min(4, cpu_count))
    if "GUNICORN_WORKERS" in os.environ:
        return _env_int("GUNICORN_WORKERS", default_workers)
    if "WEB_CONCURRENCY" in os.environ:
        return _env_int("WEB_CONCURRENCY", default_workers)
    return default_workers


# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
backlog = _env_int("GUNICORN_BACKLOG", 2048)

# Worker processes - use sync for stability with threading
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "sync")
workers = _configured_workers()
# worker_connections not needed for sync workers

# Timeouts and keepalive
timeout = _env_int("GUNICORN_TIMEOUT", 30)
keepalive = _env_int("GUNICORN_KEEPALIVE", 2)

# Resource limits
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)

# Preload application for memory efficiency
preload_app = True

# Logging
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
errorlog = "-"
accesslog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Process naming
proc_name = "batchtrack"

# Security
limit_request_line = 8192
limit_request_fields = 100
limit_request_field_size = 8192

print(
    f"Gunicorn config: {workers} {worker_class} workers, "
    f"{worker_connections} connections each"
)
