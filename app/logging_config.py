
import logging
import os
from flask import Flask
import re

class PiiRedactionFilter(logging.Filter):
    """Redact common PII patterns from log messages."""

    EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    TOKEN_RE = re.compile(r"(token|api[_-]?key|secret|password|passwd|authorization)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)
    BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-_.=:+/]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            # Redact emails
            msg = self.EMAIL_RE.sub("[REDACTED_EMAIL]", msg)
            # Redact key=value tokens
            msg = self.TOKEN_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", msg)
            # Redact bearer tokens
            msg = self.BEARER_RE.sub("Bearer [REDACTED]", msg)
            record.msg = msg
        except Exception:
            # Never break logging
            pass
        return True


def configure_logging(app: Flask):
    """Configure application logging based on environment with optional PII redaction."""

    def _coerce_level(value):
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            candidate = value.strip().upper()
            return getattr(logging, candidate, logging.INFO)
        return logging.INFO

    # Get log level from config (default WARNING for cleaner output)
    raw_level = app.config.get('LOG_LEVEL', 'WARNING' if app.config.get('DEBUG') else 'INFO')
    effective_level = _coerce_level(raw_level)

    # Set root logger level
    logging.getLogger().setLevel(effective_level)

    # Configure Flask's logger
    app.logger.setLevel(effective_level)
    
    # Prevent duplicate logging by disabling propagation for app loggers
    app_logger = logging.getLogger('app')
    app_logger.propagate = False
    
    # Clear any existing handlers to prevent duplicates
    for handler in app_logger.handlers[:]:
        app_logger.removeHandler(handler)

    # Silence noisy third-party loggers unless debugging explicitly enabled
    if effective_level > logging.DEBUG:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('flask_limiter').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Configure format
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        # Production format - clean and structured
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
    else:
        # Development format - more detailed
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
        )
    
    # Apply formatter and optional PII redaction to all handlers
    redact_pii = app.config.get('LOG_REDACT_PII', True)
    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
        if redact_pii:
            handler.addFilter(PiiRedactionFilter())

    # Also apply to root logger handlers (e.g., gunicorn)
    for handler in logging.getLogger().handlers:
        try:
            handler.setFormatter(formatter)
            if redact_pii:
                handler.addFilter(PiiRedactionFilter())
        except Exception:
            continue
