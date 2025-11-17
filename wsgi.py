import os
import sys


def _gevent_patch_kwargs():
    """
    [PATCH-001] Avoid patching Python's threading subsystem on Python 3.13+
    because gevent 24.x triggers KeyError/AssertionError callbacks when
    wrapping threading.Timer. Allow opt-in overrides via GEVENT_PATCH_THREADS.
    See docs/operations/PATCHES.md for details.
    """
    env_value = os.environ.get("GEVENT_PATCH_THREADS")
    should_patch_threads: bool

    if env_value is not None:
        normalized = env_value.strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            should_patch_threads = True
        elif normalized in {"0", "false", "off", "no"}:
            should_patch_threads = False
        else:
            # Fall back to default if value is malformed
            should_patch_threads = sys.version_info < (3, 13)
    else:
        should_patch_threads = sys.version_info < (3, 13)

    if should_patch_threads:
        return {}

    # Don't let gevent wrap threading/_thread; native timers stay stable.
    return {"thread": False, "threading": False}


try:
    from gevent import monkey  # type: ignore

    monkey.patch_all(**_gevent_patch_kwargs())
except Exception:
    # gevent may not be installed in local/dev environments
    pass

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=bool(app.config.get('DEBUG')))
