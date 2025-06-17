from flask import current_app
from flask_login import current_user
from datetime import datetime, timedelta
from ..models import InventoryItem, InventoryHistory
from ..extensions import db