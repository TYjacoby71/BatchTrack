from __future__ import annotations

import logging
import os
import re
from typing import Iterable

from flask import Flask

DEV_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
PROD_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+"),
    "token": re.compile(r"(token|api[_-]?key|secret|password|passwd|authorization)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9\-_.=:+/]+", re.IGNORECASE),
}


class PiiRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - defensive
        try:
            msg = record.getMessage()
            msg = PII_PATTERNS["email"].sub("[REDACTED_EMAIL]", msg)
            msg = PII_PATTERNS["token"].sub(lambda m: f"{m.group(1)}=[REDACTED]", msg)
            msg = PII_PATTERNS["bearer"].sub("Bearer [REDACTED]", msg)
            record.msg = msg
        except Exception:
            pass
        return True


def configure_logging(app: Flask) -> None:
    level = _coerce_level(app.config.get("LOG_LEVEL", "DEBUG" if app.debug else "INFO"))
    logging.getLogger().setLevel(level)
    app.logger.setLevel(level)

    app_logger = logging.getLogger("app")
    app_logger.propagate = False
    for handler in app_logger.handlers[:]:
        app_logger.removeHandler(handler)

    if level > logging.DEBUG:
        for noisy in ("werkzeug", "flask_limiter", "sqlalchemy.engine", "app.blueprints_registry"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    is_production = app.config.get("ENV") == "production" and not app.debug
    formatter = logging.Formatter(PROD_FORMAT if is_production else DEV_FORMAT)
    redact_pii = app.config.get("LOG_REDACT_PII", True)
    _apply_formatter(logging.getLogger().handlers, formatter, redact_pii)
    _apply_formatter(app.logger.handlers, formatter, redact_pii)


def _apply_formatter(handlers: Iterable[logging.Handler], formatter: logging.Formatter, redact_pii: bool) -> None:
    for handler in handlers:
        try:
            handler.setFormatter(formatter)
            if redact_pii:
                handler.addFilter(PiiRedactionFilter())
        except Exception:  # pragma: no cover
            continue


def _coerce_level(raw_level) -> int:
    if isinstance(raw_level, int):
        return raw_level
    if isinstance(raw_level, str):
        candidate = raw_level.strip().upper()
        return getattr(logging, candidate, logging.INFO)
    return logging.INFO
