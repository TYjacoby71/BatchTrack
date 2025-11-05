
#!/usr/bin/env python3
"""BatchTrack development entry point.

This module intentionally only exposes Flask's built-in development server. In
production and staging environments you **must** run the application through a
real WSGI server such as Gunicorn: `gunicorn --config gunicorn.conf.py wsgi:app`.
"""

import logging
import os
import sys

from app import create_app

app = create_app()


def _resolve_log_level(raw_level):
    if isinstance(raw_level, str):
        candidate = raw_level.strip().upper()
        return getattr(logging, candidate, logging.INFO)
    if isinstance(raw_level, int):
        return raw_level
    return logging.INFO


def _resolve_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _env_name() -> str:
    explicit = os.environ.get('FLASK_ENV') or os.environ.get('ENV')
    if explicit:
        return explicit.strip().lower()
    return str(app.config.get('ENV', '')).strip().lower() or 'production'


def _should_block_dev_server(env_name: str, debug_enabled: bool) -> bool:
    if debug_enabled:
        return False

    allow_override = _resolve_bool(os.environ.get('ALLOW_DEV_SERVER_IN_PRODUCTION'))
    if allow_override:
        return False

    return env_name in {'production', 'staging'}


if __name__ == '__main__':
    env_name = _env_name()
    debug_enabled = _resolve_bool(app.config.get('DEBUG'), default=(env_name == 'development'))

    if _should_block_dev_server(env_name, debug_enabled):
        sys.stderr.write(
            "\n🚫  Refusing to launch Flask's development server in a production-like "
            f"environment ({env_name!r}).\n"
            "    Use a WSGI server instead, for example:\n"
            "        gunicorn --bind 0.0.0.0:5000 --workers 4 wsgi:app\n"
            "\n    Set ALLOW_DEV_SERVER_IN_PRODUCTION=1 to override (not recommended).\n\n"
        )
        raise SystemExit(2)

    effective_level = _resolve_log_level(
        app.config.get('LOG_LEVEL', 'DEBUG' if debug_enabled else 'INFO')
    )

    logging.basicConfig(
        level=effective_level,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    app.logger.setLevel(effective_level)

    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))

    app.run(host=host, port=port, debug=debug_enabled, threaded=True, use_reloader=debug_enabled)
