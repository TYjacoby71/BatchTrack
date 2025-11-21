from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any

from app.utils.json_store import read_json_file

SETTINGS_FILE = "settings.json"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"


def get_setting(key: str, default: Any | None = None) -> Any | None:
    """Return a configuration value stored in the shared JSON settings file."""
    data = read_json_file(SETTINGS_FILE, default={}) or {}
    return data.get(key, default)


def setup_logging(app, *, log_dir: str = "logs", filename: str = "batchtrack.log") -> None:
    """
    Configure a rotating file handler for the application logger.

    Idempotent: calling multiple times will not attach duplicate handlers.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    if any(isinstance(handler, RotatingFileHandler) and handler.baseFilename == log_path
           for handler in app.logger.handlers):
        return

    file_handler = RotatingFileHandler(log_path, maxBytes=10_240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("BatchTrack startup")
