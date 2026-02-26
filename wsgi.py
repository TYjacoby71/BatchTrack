import logging
import os
import sys

from app import create_app

LOG = logging.getLogger(__name__)
_TRUTHY = {"1", "true", "on", "yes"}
_FALSY = {"0", "false", "off", "no"}


def _running_under_gunicorn() -> bool:
    """Best-effort detection to avoid duplicate monkey patching under Gunicorn."""
    server_software = (os.environ.get("SERVER_SOFTWARE") or "").strip().lower()
    if "gunicorn" in server_software:
        return True

    if os.environ.get("GUNICORN_CMD_ARGS"):
        return True

    argv0 = (sys.argv[0] if sys.argv else "").strip().lower()
    return "gunicorn" in argv0


def _gevent_patch_kwargs() -> dict[str, bool]:
    """Skip gevent's thread patching on Python 3.13+ unless explicitly enabled."""
    env_value = os.environ.get("GEVENT_PATCH_THREADS")

    if env_value is not None:
        normalized = env_value.strip().lower()
        if normalized in _TRUTHY:
            return {}
        if normalized in _FALSY:
            return {"thread": False, "threading": False}

    should_patch_threads = sys.version_info < (3, 13)
    return {} if should_patch_threads else {"thread": False, "threading": False}


try:
    from gevent import monkey  # type: ignore

    if not _running_under_gunicorn():
        monkey.patch_all(**_gevent_patch_kwargs())
except Exception as err:  # pragma: no cover - best effort import
    LOG.debug("gevent monkey patching skipped: %s", err)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=bool(app.config.get("DEBUG")))
