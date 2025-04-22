
from models import Unit
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(app):
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    file_handler = RotatingFileHandler('logs/batchtrack.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('BatchTrack startup')

def get_global_unit_list():
    """Returns all units ordered by type and custom flag."""
    return Unit.query.order_by(Unit.type, Unit.is_custom, Unit.name).all()
