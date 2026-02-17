from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
from .mixins import ScopedModelMixin


class IngredientCategory(ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(
        db.String(7), default="#6c757d"
    )  # Bootstrap secondary color (hex)
    default_density = db.Column(
        db.Float, nullable=True
    )  # Default density for category in g/ml
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    # Global category integration
    is_global_category = db.Column(
        db.Boolean, default=False
    )  # True if this is a global/reference category (seeded from JSON)


class InventoryCategory(ScopedModelMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    # item_type delineates which inventory item type this category applies to
    # Expected values include: 'ingredient', 'container', 'packaging', 'consumable'
    item_type = db.Column(db.String(32), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    __table_args__ = (
        # Unique per organization and type to avoid duplicates
        db.UniqueConstraint(
            "name", "item_type", "organization_id", name="_invcat_name_type_org_uc"
        ),
    )


class Tag(ScopedModelMixin, db.Model):
    """Tags for categorizing batches, products, etc."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    color = db.Column(db.String(7), default="#6c757d")  # hex color
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Add unique constraint per organization
    __table_args__ = (
        db.UniqueConstraint("name", "organization_id", name="_tag_name_org_uc"),
    )
