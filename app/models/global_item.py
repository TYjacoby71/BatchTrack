from sqlalchemy import event

from ..extensions import db
from ..utils.seo import slugify_value
from ..utils.timezone_utils import TimezoneUtils
from .db_dialect import is_postgres
from app.services.cache_invalidation import invalidate_global_library_cache

class GlobalItem(db.Model):
    __tablename__ = 'global_item'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    item_type = db.Column(db.String(32), nullable=False, index=True)  # ingredient, container, packaging, consumable
    aliases = db.Column(db.JSON, nullable=True)  # list of strings for alternative names
    density = db.Column(db.Float, nullable=True)  # g/ml
    default_unit = db.Column(db.String(32), nullable=True)

    # Category relationship - proper FK to IngredientCategory
    ingredient_category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'), nullable=True, index=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=True, index=True)
    variation_id = db.Column(db.Integer, db.ForeignKey('variation.id'), nullable=True, index=True)

    # Perishable information
    default_is_perishable = db.Column(db.Boolean, nullable=True, default=False)
    recommended_shelf_life_days = db.Column(db.Integer, nullable=True)
    recommended_fragrance_load_pct = db.Column(db.String(64), nullable=True)
    is_active_ingredient = db.Column(db.Boolean, nullable=False, default=False)

    # Regulatory / labeling
    inci_name = db.Column(db.String(256), nullable=True)
    cas_number = db.Column(db.String(64), nullable=True)
    certifications = db.Column(db.JSON, nullable=True)

    # Container/packaging specific fields
    capacity = db.Column(db.Float, nullable=True)
    capacity_unit = db.Column(db.String(32), nullable=True)
    container_material = db.Column(db.String(64), nullable=True)
    container_type = db.Column(db.String(64), nullable=True)
    container_style = db.Column(db.String(64), nullable=True)
    container_color = db.Column(db.String(64), nullable=True)

    # Soap making and cosmetic formulation fields
    saponification_value = db.Column(db.Float, nullable=True)  # SAP value for oils/fats
    iodine_value = db.Column(db.Float, nullable=True)  # Iodine value for oils
    melting_point_c = db.Column(db.Float, nullable=True)  # Melting point in Celsius
    flash_point_c = db.Column(db.Float, nullable=True)  # Flash point for essential oils
    ph_value = db.Column(db.String(32), nullable=True)  # pH for liquids (display)
    ph_min = db.Column(db.Float, nullable=True)  # Minimum pH value
    ph_max = db.Column(db.Float, nullable=True)  # Maximum pH value
    moisture_content_percent = db.Column(db.Float, nullable=True)  # Moisture content
    comedogenic_rating = db.Column(db.Integer, nullable=True)  # 0-5 scale for oils
    fatty_acid_profile = db.Column(db.JSON, nullable=True)

    # Baking attributes
    protein_content_pct = db.Column(db.Float, nullable=True)

    # Brewing attributes
    brewing_color_srm = db.Column(db.Float, nullable=True)
    brewing_potential_sg = db.Column(db.Float, nullable=True)
    brewing_diastatic_power_lintner = db.Column(db.Float, nullable=True)

    # SEO and metadata
    metadata_json = db.Column(db.JSON, nullable=True)  # For SEO, descriptions, etc.

    # Soft-delete/archive flags
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now, nullable=False)

    # Relationships
    ingredient_category = db.relationship('IngredientCategory', backref='global_items')
    ingredient = db.relationship(
        'IngredientDefinition',
        backref=db.backref('global_items', lazy='dynamic'),
    )
    variation = db.relationship(
        'Variation',
        backref=db.backref('global_items', lazy='dynamic'),
        foreign_keys=[variation_id],
    )

    @property
    def physical_form(self):
        """Backwards-compatible accessor referencing the variation's physical form."""
        return self.variation.physical_form if getattr(self, "variation", None) else None

    @physical_form.setter
    def physical_form(self, value):
        """Allow legacy code paths to continue assigning physical forms directly."""
        if value is None:
            self.variation = None
            return

        from app.models.ingredient_reference import PhysicalForm, Variation

        if isinstance(value, Variation):
            self.variation = value
            return

        if not isinstance(value, PhysicalForm):
            raise TypeError("physical_form must be a PhysicalForm or Variation instance")

        variation = (
            Variation.query.filter_by(physical_form_id=value.id)
            .order_by(Variation.id.asc())
            .first()
        )
        if not variation:
            slug = slugify_value(value.slug or value.name or "variation")
            variation = Variation(
                name=value.name or slug or f"variation-{value.id}",
                slug=slug or f"variation-{value.id}",
                physical_form=value,
                description=value.description,
                is_active=value.is_active,
            )
            db.session.add(variation)
        self.variation = variation

    @property
    def physical_form_id(self):
        """Expose variation's physical form id for compatibility."""
        physical_form = self.physical_form
        return physical_form.id if physical_form else None

    @physical_form_id.setter
    def physical_form_id(self, value):
        if value in (None, ""):
            self.variation = None
            return
        from app.models.ingredient_reference import PhysicalForm

        try:
            form_obj = PhysicalForm.query.get(int(value))
        except (TypeError, ValueError):
            form_obj = None
        if not form_obj:
            raise ValueError("Invalid physical form id")
        self.physical_form = form_obj
    functions = db.relationship(
        'FunctionTag',
        secondary='global_item_function_tag',
        back_populates='global_items',
    )
    applications = db.relationship(
        'ApplicationTag',
        secondary='global_item_application_tag',
        back_populates='global_items',
    )
    category_tags = db.relationship(
        'IngredientCategoryTag',
        secondary='global_item_category_tag',
        back_populates='global_items',
    )
    archived_by_user = db.relationship('User', foreign_keys=[archived_by])

    _IS_PG = is_postgres()

    _table_args = [
        db.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
        db.Index('ix_global_item_archive_type_name', 'is_archived', 'item_type', 'name'),
    ]
    if _IS_PG:
        _table_args.append(
            db.Index(
                'ix_global_item_aliases_gin',
                db.text('(aliases::jsonb)'),
                postgresql_using='gin',
            )
        )
    __table_args__ = tuple(_table_args)


def _apply_metadata_defaults(target):
    try:
        from app.services.global_item_metadata_service import GlobalItemMetadataService
    except Exception:
        return

    new_metadata = GlobalItemMetadataService.merge_metadata(target)
    if new_metadata != (target.metadata_json or {}):
        target.metadata_json = new_metadata


@event.listens_for(GlobalItem, "before_insert")
def _global_item_metadata_before_insert(mapper, connection, target):
    _apply_metadata_defaults(target)


@event.listens_for(GlobalItem, "before_update")
def _global_item_metadata_before_update(mapper, connection, target):
    _apply_metadata_defaults(target)


@event.listens_for(GlobalItem, "after_insert")
def _global_item_after_insert(mapper, connection, target):
    invalidate_global_library_cache()


@event.listens_for(GlobalItem, "after_update")
def _global_item_after_update(mapper, connection, target):
    invalidate_global_library_cache()


@event.listens_for(GlobalItem, "after_delete")
def _global_item_after_delete(mapper, connection, target):
    invalidate_global_library_cache()