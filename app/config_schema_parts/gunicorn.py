"""Config schema: Gunicorn settings.

Synopsis:
Defines Gunicorn worker and timeout configuration keys.

Glossary:
- Gunicorn: WSGI server used to run the Flask app in production.
"""

# --- Gunicorn fields ---
# Purpose: Provide Gunicorn configuration definitions.
FIELDS = [
    {
        "key": "GUNICORN_WORKERS",
        "cast": "int",
        "default": 2,
        "description": "Gunicorn worker count.",
        "recommended": "2",
    },
    {
        "key": "GUNICORN_WORKER_CLASS",
        "cast": "str",
        "default": "gevent",
        "description": "Gunicorn worker class.",
        "recommended": "gevent",
    },
    {
        "key": "GUNICORN_WORKER_CONNECTIONS",
        "cast": "int",
        "default": 2000,
        "description": "Gunicorn worker connection limit.",
        "recommended": "1000",
    },
    {
        "key": "GUNICORN_TIMEOUT",
        "cast": "int",
        "default": 60,
        "description": "Gunicorn worker timeout in seconds.",
        "recommended": "30",
    },
    {
        "key": "GUNICORN_KEEPALIVE",
        "cast": "int",
        "default": 5,
        "description": "Gunicorn keepalive seconds.",
        "recommended": "2",
    },
    {
        "key": "GUNICORN_MAX_REQUESTS",
        "cast": "int",
        "default": 2000,
        "description": "Gunicorn max requests before recycle.",
        "recommended": "2000",
    },
    {
        "key": "GUNICORN_MAX_REQUESTS_JITTER",
        "cast": "int",
        "default": 100,
        "description": "Gunicorn max requests jitter.",
        "recommended": "100",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "GUNICORN_BACKLOG",
        "cast": "int",
        "default": 2048,
        "description": "Gunicorn socket backlog.",
        "recommended": "2048",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "GUNICORN_LOG_LEVEL",
        "cast": "str",
        "default": "info",
        "description": "Gunicorn log level.",
        "recommended": "info",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "GUNICORN_PRELOAD_APP",
        "cast": "bool",
        "default": False,
        "description": "Preload the app before forking workers.",
        "recommended": "0",
    },
]

# --- Gunicorn section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "gunicorn",
    "title": "Gunicorn Server",
    "note": "Server process settings for Gunicorn.",
}
