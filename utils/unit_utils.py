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
    try:
        units = Unit.query.filter_by(is_custom=False).order_by(Unit.type, Unit.name).all()
        custom_units = Unit.query.filter_by(is_custom=True).order_by(Unit.name).all()
        return units + custom_units
    except Exception as e:
        return []