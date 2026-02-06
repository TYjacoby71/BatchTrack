#!/usr/bin/env python3
"""Local development entry point.

Synopsis:
Runs the Flask dev server for local/ad-hoc use (not production).

Glossary:
- Dev server: Flask's built-in server for local debugging.
- WSGI: Production server interface (e.g., Gunicorn).
"""

import logging
import os
import sys
from typing import Final

from app import create_app

LOG: Final = logging.getLogger("run")
app = create_app()

_TRUTHY = {"1", "true", "on", "yes"}


def _env_flag(name: str, default: bool = False) -> bool:
    """Return True when the named environment variable is truthy."""
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in _TRUTHY


def _configure_logging(debug_enabled: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug_enabled else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    if debug_enabled:
        app.logger.setLevel(logging.DEBUG)


def main() -> None:
    env = os.environ.get("FLASK_ENV", "development").lower()
    debug_enabled = env != "production"

    if env == "production" and not _env_flag("ALLOW_DEV_SERVER_IN_PRODUCTION"):
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
        LOG.error(
            "Refusing to start the Flask dev server while FLASK_ENV=production. "
            "Run a WSGI server instead, e.g. `gunicorn wsgi:app`.",
        )
        raise SystemExit(2)

    _configure_logging(debug_enabled)

    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )


if __name__ == "__main__":
    main()
