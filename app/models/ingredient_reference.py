from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class IngredientDefinition(db.Model):
    """Canonical ingredient entity that groups one or more global items/forms."""

    __tablename__ = 'ingredient'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(128), nullable=True, unique=True, index=True)
    inci_name = db.Column(db.String(256), nullable=True)
    cas_number = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=True)
    ingredient_category_id = db.Column(
        db.Integer, db.ForeignKey('ingredient_category.id', ondelete='SET NULL'), nullable=True
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    category = db.relationship('IngredientCategory', backref='ingredient_definitions')


class PhysicalForm(db.Model):
    """Lookup table for physical forms such as Powder, Whole Leaf, Liquid, etc."""

    __tablename__ = 'physical_form'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    slug = db.Column(db.String(64), nullable=True, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )


class Variation(db.Model):
    """Curated purchasable variations (e.g., Powder, Whole Fresh, 2% Liquid) with physical form metadata."""

    __tablename__ = 'variation'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=True, unique=True, index=True)
    physical_form_id = db.Column(
        db.Integer,
        db.ForeignKey('physical_form.id', ondelete='SET NULL'),
        nullable=True,
    )
    description = db.Column(db.Text, nullable=True)
    default_unit = db.Column(db.String(32), nullable=True)
    form_bypass = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    physical_form = db.relationship(
        'PhysicalForm',
        backref=db.backref('variations', lazy='dynamic'),
    )


class FunctionTag(db.Model):
    """Functional classifications (e.g., Humectant, Emulsifier)."""

    __tablename__ = 'function_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    slug = db.Column(db.String(64), nullable=True, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    global_items = db.relationship(
        'GlobalItem',
        secondary='global_item_function_tag',
        back_populates='functions',
    )


class ApplicationTag(db.Model):
    """Application classifications (e.g., Cold Process Soap, Lotion, Bakery Bread)."""

    __tablename__ = 'application_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=True, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    global_items = db.relationship(
        'GlobalItem',
        secondary='global_item_application_tag',
        back_populates='applications',
    )


class IngredientCategoryTag(db.Model):
    """Flexible tagging layer derived from legacy ingredient categories."""

    __tablename__ = 'ingredient_category_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=True, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    global_items = db.relationship(
        'GlobalItem',
        secondary='global_item_category_tag',
        back_populates='category_tags',
    )


class GlobalItemFunctionTag(db.Model):
    """Association table linking global items to function tags."""

    __tablename__ = 'global_item_function_tag'

    id = db.Column(db.Integer, primary_key=True)
    global_item_id = db.Column(
        db.Integer,
        db.ForeignKey('global_item.id', ondelete='CASCADE'),
        nullable=False,
    )
    function_tag_id = db.Column(
        db.Integer,
        db.ForeignKey('function_tag.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'global_item_id',
            'function_tag_id',
            name='uq_global_item_function_tag',
        ),
        db.Index('ix_global_item_function_tag_item', 'global_item_id'),
        db.Index('ix_global_item_function_tag_function', 'function_tag_id'),
    )


class GlobalItemApplicationTag(db.Model):
    """Association table linking global items to application tags."""

    __tablename__ = 'global_item_application_tag'

    id = db.Column(db.Integer, primary_key=True)
    global_item_id = db.Column(
        db.Integer,
        db.ForeignKey('global_item.id', ondelete='CASCADE'),
        nullable=False,
    )
    application_tag_id = db.Column(
        db.Integer,
        db.ForeignKey('application_tag.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'global_item_id',
            'application_tag_id',
            name='uq_global_item_application_tag',
        ),
        db.Index('ix_global_item_application_tag_item', 'global_item_id'),
        db.Index('ix_global_item_application_tag_application', 'application_tag_id'),
    )


class GlobalItemCategoryTag(db.Model):
    """Association table linking global items to flexible ingredient category tags."""

    __tablename__ = 'global_item_category_tag'

    id = db.Column(db.Integer, primary_key=True)
    global_item_id = db.Column(
        db.Integer,
        db.ForeignKey('global_item.id', ondelete='CASCADE'),
        nullable=False,
    )
    ingredient_category_tag_id = db.Column(
        db.Integer,
        db.ForeignKey('ingredient_category_tag.id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'global_item_id',
            'ingredient_category_tag_id',
            name='uq_global_item_category_tag',
        ),
        db.Index('ix_global_item_category_tag_item', 'global_item_id'),
        db.Index('ix_global_item_category_tag_category', 'ingredient_category_tag_id'),
    )
