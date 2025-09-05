from ..extensions import db
from .mixins import ScopedModelMixin

class GlobalItem(db.Model):
	__tablename__ = 'global_item'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(128), nullable=False, index=True)
	item_type = db.Column(db.String(32), nullable=False, index=True)  # ingredient, container, packaging, consumable
	default_unit = db.Column(db.String(32), nullable=True)
	# Ingredient-specific
	density = db.Column(db.Float, nullable=True)  # g/ml
	# Curated category relation (single source of truth)
	ingredient_category_id = db.Column(db.Integer, db.ForeignKey('ingredient_category.id'), nullable=True, index=True)
	# Deprecated: previous string-based category
	reference_category = db.Column(db.String(64), nullable=True)
	# Container/packaging defaults (nullable for packaging per requirement)
	capacity = db.Column(db.Float, nullable=True)
	capacity_unit = db.Column(db.String(32), nullable=True)
	# Perishable defaults
	default_is_perishable = db.Column(db.Boolean, nullable=True)
	recommended_shelf_life_days = db.Column(db.Integer, nullable=True)
	# Category hint: optional linkage to inventory category taxonomy
	suggested_inventory_category_id = db.Column(db.Integer, db.ForeignKey('inventory_category.id'), nullable=True)
	# Free-form metadata for future-proofing
	metadata_json = db.Column(db.JSON, nullable=True)
	# Synonyms/other names for search and display
	aka_names = db.Column(db.JSON, nullable=True)  # list of strings

	# Soft-delete/archive flags
	is_archived = db.Column(db.Boolean, nullable=False, default=False)
	archived_at = db.Column(db.DateTime, nullable=True)
	archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

	suggested_inventory_category = db.relationship('InventoryCategory')
	ingredient_category = db.relationship('IngredientCategory')
	archived_by_user = db.relationship('User', foreign_keys=[archived_by])

	__table_args__ = (
		db.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
	)