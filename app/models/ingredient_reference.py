from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class IngredientProfile(db.Model):
    """Canonical ingredient definition that groups related global items."""
    __tablename__ = 'ingredient'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, unique=True)
    inci_name = db.Column(db.String(255), nullable=True)
    cas_number = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=True)
    aliases = db.Column(db.JSON, nullable=True)
    is_active_ingredient = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    __table_args__ = (
        db.Index('ix_ingredient_slug', 'slug', unique=True),
    )

    def __repr__(self):
        return f"<IngredientProfile id={self.id} name={self.name!r}>"


class PhysicalForm(db.Model):
    """Controlled vocabulary for physical form selections (powder, whole, liquid, etc.)."""
    __tablename__ = 'physical_form'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    __table_args__ = (
        db.Index('ix_physical_form_slug', 'slug', unique=True),
    )

    def __repr__(self):
        return f"<PhysicalForm id={self.id} name={self.name!r}>"


class FunctionTag(db.Model):
    """Functional classification tags (e.g., antioxidant, surfactant)."""
    __tablename__ = 'function_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('function_tag.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    parent = db.relationship('FunctionTag', remote_side=[id], backref='children')
    global_items = db.relationship(
        'GlobalItem',
        secondary='global_item_function_tag',
        back_populates='function_tags',
    )

    __table_args__ = (
        db.Index('ix_function_tag_slug', 'slug', unique=True),
    )

    def __repr__(self):
        return f"<FunctionTag id={self.id} name={self.name!r}>"


class ApplicationTag(db.Model):
    """Application/usage classification tags (e.g., skin care > serums)."""
    __tablename__ = 'application_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    slug = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('application_tag.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    parent = db.relationship('ApplicationTag', remote_side=[id], backref='children')
    global_items = db.relationship(
        'GlobalItem',
        secondary='global_item_application_tag',
        back_populates='application_tags',
    )

    __table_args__ = (
        db.Index('ix_application_tag_slug', 'slug', unique=True),
    )

    def __repr__(self):
        return f"<ApplicationTag id={self.id} name={self.name!r}>"


class GlobalItemFunctionTag(db.Model):
    """Association table of global item ↔ function tag."""
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
        db.UniqueConstraint('global_item_id', 'function_tag_id', name='uq_global_item_function_tag'),
        db.Index('ix_global_item_function_tag_item', 'global_item_id'),
        db.Index('ix_global_item_function_tag_tag', 'function_tag_id'),
    )


class GlobalItemApplicationTag(db.Model):
    """Association table of global item ↔ application tag."""
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
        db.UniqueConstraint('global_item_id', 'application_tag_id', name='uq_global_item_application_tag'),
        db.Index('ix_global_item_application_tag_item', 'global_item_id'),
        db.Index('ix_global_item_application_tag_tag', 'application_tag_id'),
    )

