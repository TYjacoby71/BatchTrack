
from datetime import datetime
from ..extensions import db

class ConversionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(32), nullable=False)
    to_amount = db.Column(db.Float, nullable=False)
    to_unit = db.Column(db.String(32), nullable=False)
    conversion_factor = db.Column(db.Float, nullable=False)
    ingredient_name = db.Column(db.String(128))
    density_used = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', backref='conversion_logs')
