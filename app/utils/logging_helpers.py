from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "batchtrack.log"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"


def setup_logging(app: Any, *, log_dir: str = DEFAULT_LOG_DIR, filename: str = DEFAULT_LOG_FILE) -> None:
    """
    Configure a rotating file handler on the provided Flask app logger.

    Acts as a legacy shim for older scripts that expect the helper in utils.py.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    if any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", None) == log_path
        for handler in app.logger.handlers
    ):
        return

    file_handler = RotatingFileHandler(log_path, maxBytes=10_240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("BatchTrack startup")
