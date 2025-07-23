
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    symbol = db.Column(db.String(16), nullable=False)
    type = db.Column(db.String(32), nullable=False)  # weight, volume, count, etc.
    base_unit = db.Column(db.String(64), nullable=True)  # For conversions
    conversion_factor = db.Column(db.Float, nullable=True)  # To base unit
    is_active = db.Column(db.Boolean, default=True)
    is_custom = db.Column(db.Boolean, default=False)
    is_mapped = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)  # Only for custom units
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Add unique constraints
    __table_args__ = (
        # Standard units (is_custom=False) must have unique names globally
        db.Index('ix_unit_standard_unique', 'name', unique=True),
        # Custom units must have unique names within organization  
        db.UniqueConstraint('name', 'name', 'organization_id', name='_unit_name_org_uc'),
    )

    @classmethod
    def scoped(cls):
        """Return query filtered by current user's organization for custom units only"""
        if not current_user.is_authenticated:
            return cls.query.filter(False)  # Return empty query if no user
        # Return all standard units + user's custom units
        return cls.query.filter(
            (cls.is_custom == False) | 
            (cls.organization_id == current_user.organization_id)
        )

    def belongs_to_user(self):
        """Check if this record belongs to the current user's organization (for custom units only)"""
        if not self.is_custom:
            return True  # Standard units belong to everyone
        if not current_user.is_authenticated:
            return False
        return self.organization_id == current_user.organization_id

class CustomUnitMapping(ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    conversion_factor = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

class ConversionLog(ScopedModelMixin, db.Model):
    __tablename__ = 'conversion_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(32), nullable=False)
    to_unit = db.Column(db.String(32), nullable=False)
    result = db.Column(db.Float, nullable=False)
    conversion_type = db.Column(db.String(64), nullable=False)
    ingredient_name = db.Column(db.String(128), nullable=True)

    user = db.relationship('User', backref='conversion_logs')
