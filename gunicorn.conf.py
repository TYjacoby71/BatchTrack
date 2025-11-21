"""Gunicorn runtime configuration used by BatchTrack deployments."""

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configured_workers() -> int:
    cpu_count = max(multiprocessing.cpu_count(), 1)
    default_workers = max(1, min(4, cpu_count))
    if "GUNICORN_WORKERS" in os.environ:
        return _env_int("GUNICORN_WORKERS", default_workers)
    if "WEB_CONCURRENCY" in os.environ:
        return _env_int("WEB_CONCURRENCY", default_workers)
    return default_workers


bind = f"0.0.0.0:{_env_int('PORT', 5000)}"
backlog = _env_int("GUNICORN_BACKLOG", 2048)

worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gevent")
workers = _configured_workers()
worker_connections = _env_int("GUNICORN_WORKER_CONNECTIONS", 1000)

timeout = _env_int("GUNICORN_TIMEOUT", 30)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", timeout)
keepalive = _env_int("GUNICORN_KEEPALIVE", 2)

max_requests = _env_int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)

preload_app = _env_bool("GUNICORN_PRELOAD", True)

access_log_format = '%(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

proc_name = os.getenv("GUNICORN_PROC_NAME", "batchtrack")

limit_request_line = 8192
limit_request_fields = 100
limit_request_field_size = 8192

worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR")
capture_output = _env_bool("GUNICORN_CAPTURE_OUTPUT", True)
