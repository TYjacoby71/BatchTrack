
from app.utils.json_store import read_json_file


def get_setting(key, default=None):
    data = read_json_file("settings.json", default={}) or {}
    return data.get(key, default)
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
