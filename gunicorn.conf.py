from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from typing import Final

LOGGER: Final = logging.getLogger("gunicorn.config")


def _env_int(key: str, default: int) -> int:
    """Parse integer environment values with sane fallbacks."""
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _configured_workers() -> int:
    """Respect explicit worker counts while preventing overcommit."""
    cpu_count = max(multiprocessing.cpu_count(), 1)
    # Default to a conservative 2x CPU with sensible caps for shared cores
    auto_workers = max(2, min(8, cpu_count * 2))

    if "GUNICORN_WORKERS" in os.environ:
        return _env_int("GUNICORN_WORKERS", auto_workers)
    if "WEB_CONCURRENCY" in os.environ:
        return _env_int("WEB_CONCURRENCY", auto_workers)

    max_auto = _env_int("GUNICORN_MAX_WORKERS", auto_workers)
    return min(auto_workers, max_auto)


def _log_runtime_configuration() -> None:
    summary = (
        f"Gunicorn bind={bind} class={worker_class} workers={workers} "
        f"connections={worker_connections} timeout={timeout}s backlog={backlog}"
    )
    try:
        if LOGGER.handlers:
            LOGGER.info(summary)
        else:
            raise RuntimeError("no handlers")
    except Exception:
        sys.stderr.write(summary + "\n")


# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
backlog = _env_int("GUNICORN_BACKLOG", 2048)

# Worker processes - use gevent for async I/O
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")
workers = _configured_workers()
worker_connections = _env_int("GUNICORN_WORKER_CONNECTIONS", 2000)

# Timeouts and keepalive
timeout = _env_int("GUNICORN_TIMEOUT", 60)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)

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

_log_runtime_configuration()
