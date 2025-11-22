import logging
import os
import sys

from app import create_app

LOG = logging.getLogger(__name__)
_TRUTHY = {"1", "true", "on", "yes"}
_FALSY = {"0", "false", "off", "no"}


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

    monkey.patch_all(**_gevent_patch_kwargs())
except Exception as err:  # pragma: no cover - best effort import
    LOG.debug("gevent monkey patching skipped: %s", err)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=bool(app.config.get("DEBUG")))
