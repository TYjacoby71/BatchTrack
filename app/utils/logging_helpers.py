from __future__ import annotations

import logging
import os
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from typing import Any

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "batchtrack.log"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"

__all__ = ["setup_logging"]


def setup_logging(
    app: Any,
    *,
    log_dir: str = DEFAULT_LOG_DIR,
    filename: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
    max_bytes: int = 1_048_576,
    backup_count: int = 10,
    add_stream_handler: bool = False,
) -> None:
    """
    Configure structured logging for the given Flask application.

    Adds a rotating file handler (and optional stream handler) only once per app,
    preserving legacy expectations for scripts that import this helper.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    file_handler_exists = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == log_path
        for handler in app.logger.handlers
    )

    if not file_handler_exists:
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        file_handler.setLevel(level)
        app.logger.addHandler(file_handler)

    if add_stream_handler and not any(
        isinstance(handler, StreamHandler) for handler in app.logger.handlers
    ):
        stream_handler = StreamHandler()
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        stream_handler.setLevel(level)
        app.logger.addHandler(stream_handler)

    app.logger.setLevel(level)
    app.logger.info("Logging configured (file: %s)", log_path)
