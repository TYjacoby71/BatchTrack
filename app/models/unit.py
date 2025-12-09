from datetime import datetime, timezone
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin, TimestampMixin
from ..utils.timezone_utils import TimezoneUtils

class Unit(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    symbol = db.Column(db.String(16))
    unit_type = db.Column(db.String(32), nullable=False)  # weight, volume, length, count, etc.
    conversion_factor = db.Column(db.Float, nullable=False, default=1.0)  # To base unit
    base_unit = db.Column(db.String(64), nullable=True)  # Reference to base unit name
    is_active = db.Column(db.Boolean, default=True)
    is_custom = db.Column(db.Boolean, default=False)  # User-created units
    is_mapped = db.Column(db.Boolean, default=False)  # Has conversion mapping
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'))
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)

    __table_args__ = (
        db.UniqueConstraint('name', 'organization_id', name='_unit_name_org_uc'),
        db.Index('ix_unit_scope', 'is_active', 'is_custom', 'organization_id'),
        db.Index('ix_unit_sort', 'unit_type', 'name'),
        db.Index('ix_unit_active_scope_sort', 'is_active', 'is_custom', 'unit_type', 'name'),
        db.Index('ix_unit_custom_org_scope', 'organization_id', 'is_active', 'is_custom', 'unit_type', 'name'),
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

    @property
    def is_base_unit(self):
        """Check if this unit is a base unit for its type"""
        return self.base_unit is None or self.base_unit == self.name
    
    @classmethod
    def get_base_units(cls):
        """Get all base units by type"""
        return cls.query.filter(
            (cls.base_unit.is_(None)) | (cls.base_unit == cls.name)
        ).all()
    
    @classmethod
    def get_base_unit_for_type(cls, unit_type):
        """Get the base unit for a specific unit type"""
        return cls.query.filter(
            cls.unit_type == unit_type,
            (cls.base_unit.is_(None)) | (cls.base_unit == cls.name)
        ).first()

class CustomUnitMapping(TimestampMixin, ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_unit = db.Column(db.String(64), nullable=False)
    to_unit = db.Column(db.String(64), nullable=False)
    conversion_factor = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class ConversionLog(TimestampMixin, ScopedModelMixin, db.Model):
    __tablename__ = 'conversion_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    from_unit = db.Column(db.String(32), nullable=False)
    to_unit = db.Column(db.String(32), nullable=False)
    result = db.Column(db.Float, nullable=False)
    conversion_type = db.Column(db.String(64), nullable=False)
    ingredient_name = db.Column(db.String(128), nullable=True)

    user = db.relationship('User', backref='conversion_logs')