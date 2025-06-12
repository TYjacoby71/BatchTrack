
from flask import flash
from models import db
from datetime import datetime

class NotificationService:
    @staticmethod
    def success(message):
        """Add success notification"""
        flash(message, 'success')
    
    @staticmethod
    def error(message):
        """Add error notification"""
        flash(message, 'error')
    
    @staticmethod
    def warning(message):
        """Add warning notification"""
        flash(message, 'warning')
    
    @staticmethod
    def info(message):
        """Add info notification"""
        flash(message, 'info')
