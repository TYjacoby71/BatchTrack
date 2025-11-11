
#!/usr/bin/env python3
"""
Application entry point using factory pattern
"""
import logging
import os
import sys

from app import create_app

app = create_app()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "on", "yes"}


if __name__ == '__main__':
    env = os.environ.get('ENV', 'development').lower()
    debug_enabled = env != 'production' and _env_flag('FLASK_DEBUG', default=True)

    if env == 'production' and not _env_flag('ALLOW_DEV_SERVER_IN_PRODUCTION'):
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
        logging.error(
            "Refusing to start the Flask dev server while ENV=production. "
            "Run a WSGI server instead, e.g. `gunicorn wsgi:app`."
        )
        raise SystemExit(2)

    logging.basicConfig(
        level=logging.DEBUG if debug_enabled else logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    if debug_enabled:
        app.logger.setLevel(logging.DEBUG)

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )
