"""Config schema: Core runtime settings.

Synopsis:
Defines environment keys that control runtime mode, URLs, and logging.

Glossary:
- Core runtime: Base settings that affect application startup behavior.
"""

# --- Core fields ---
# Purpose: Provide core runtime configuration definitions.
FIELDS = [
    {
        "key": "FLASK_ENV",
        "cast": "str",
        "default": "development",
        "description": "Runtime environment selector.",
        "required": True,
        "recommended": "production",
        "note": "Allowed values: development, testing, staging, production.",
    },
    {
        "key": "FLASK_SECRET_KEY",
        "cast": "str",
        "default": None,
        "description": "Flask session signing secret.",
        "required": True,
        "secret": True,
        "recommended": "your-secret-key-here-must-be-32-chars-minimum",
        "default_by_env": {
            "development": "devkey-please-change-in-production",
            "testing": "devkey-please-change-in-production",
        },
    },
    {
        "key": "APP_BASE_URL",
        "cast": "str",
        "default": None,
        "description": "Canonical public base URL (https://app.example.com).",
        "required_in": ("staging", "production"),
        "recommended": "https://app.example.com",
        "default_by_env": {
            "development": "http://localhost:5000",
            "testing": "http://localhost:5000",
        },
    },
    {
        "key": "APP_HOST",
        "cast": "str",
        "default": None,
        "description": "Optional explicit host override for proxy/CSRF checks.",
        "required": False,
        "recommended": "app.example.com",
    },
    {
        "key": "LOG_LEVEL",
        "cast": "str",
        "default": "WARNING",
        "description": "Application logging level.",
        "required": False,
        "recommended": "INFO",
        "default_by_env": {"staging": "INFO", "production": "INFO"},
    },
    {
        "key": "ANON_REQUEST_LOG_LEVEL",
        "cast": "str",
        "default": "DEBUG",
        "description": "Anonymous request log level override.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "LOG_REDACT_PII",
        "cast": "bool",
        "default": True,
        "description": "Enable PII redaction in logs.",
        "recommended": "true",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "ALLOW_DEV_SERVER_IN_PRODUCTION",
        "cast": "bool",
        "default": False,
        "description": "Allow running the Flask dev server in production.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
]

# --- Core section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "core",
    "title": "Core Runtime & Platform",
    "note": "Set these to lock the app into production mode before launch.",
}
