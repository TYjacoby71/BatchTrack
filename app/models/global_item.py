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
	# Reference grouping for density categories (e.g., Oils, Waxes)
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

	suggested_inventory_category = db.relationship('InventoryCategory')

	__table_args__ = (
		db.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
	)