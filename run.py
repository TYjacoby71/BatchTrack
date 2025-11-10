
#!/usr/bin/env python3
"""
Application entry point using factory pattern
"""
import logging
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


if __name__ == '__main__':
    try:
        debug_enabled = _resolve_bool(app.config.get('DEBUG'), default=False)
        effective_level = _resolve_log_level(
            app.config.get('LOG_LEVEL', 'DEBUG' if debug_enabled else 'INFO')
        )

        logging.basicConfig(
            level=effective_level,
            format='%(asctime)s %(levelname)s: %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )

        app.logger.setLevel(effective_level)
        app.logger.info('Starting BatchTrack application...')
        app.run(host='0.0.0.0', port=5000, debug=debug_enabled)
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)
