
import logging
import os
from flask import Flask

def configure_logging(app: Flask):
    """Configure application logging based on environment"""
    
    # Get log level from config
    log_level = getattr(app.config, 'LOG_LEVEL', 'INFO')
    
    # Set root logger level
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Configure Flask's logger
    app.logger.setLevel(getattr(logging, log_level))
    
    # Silence noisy third-party loggers in production
    if log_level != 'DEBUG':
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
    
    # Apply formatter to all handlers
    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
