
from datetime import datetime
from ..extensions import db

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    color = db.Column(db.String(7), default='#007bff')  # Hex color code
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
