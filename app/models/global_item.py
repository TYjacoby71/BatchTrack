
import os
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

class GlobalItem(db.Model):
	__tablename__ = 'global_item'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(128), nullable=False, index=True)
	item_type = db.Column(db.String(32), nullable=False, index=True)  # ingredient, container, packaging, consumable
	aka_names = db.Column(db.JSON, nullable=True)  # list of strings for alternative names
	density = db.Column(db.Float, nullable=True)  # g/ml
	default_unit = db.Column(db.String(32), nullable=True)

	# Category relationship - proper FK to IngredientCategory
	ingredient_category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'), nullable=True, index=True)

	# Perishable information
	default_is_perishable = db.Column(db.Boolean, nullable=True, default=False)
	recommended_shelf_life_days = db.Column(db.Integer, nullable=True)

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
	ph_value = db.Column(db.Float, nullable=True)  # pH for liquids
	moisture_content_percent = db.Column(db.Float, nullable=True)  # Moisture content
	shelf_life_months = db.Column(db.Integer, nullable=True)  # Shelf life in months
	comedogenic_rating = db.Column(db.Integer, nullable=True)  # 0-5 scale for oils

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
	archived_by_user = db.relationship('User', foreign_keys=[archived_by])

	def _is_postgres_url(url: str) -> bool:
		if not url:
			return False
		url = url.lower()
		return (
			url.startswith("postgres://")
			or url.startswith("postgresql://")
			or url.startswith("postgresql+psycopg2://")
		)

	_IS_PG = _is_postgres_url(os.environ.get("DATABASE_URL", ""))

	__table_args__ = tuple([
		db.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
		*([db.Index('ix_global_item_aka_gin', db.text('(aka_names::jsonb)'), postgresql_using='gin')] if _IS_PG else []),
	])
