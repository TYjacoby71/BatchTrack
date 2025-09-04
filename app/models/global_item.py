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
	# Container/packaging defaults (nullable for packaging per requirement)
	capacity = db.Column(db.Float, nullable=True)
	capacity_unit = db.Column(db.String(32), nullable=True)
	# Category hint: optional linkage to inventory category taxonomy
	suggested_inventory_category_id = db.Column(db.Integer, db.ForeignKey('inventory_category.id'), nullable=True)
	# Free-form metadata for future-proofing
	metadata_json = db.Column(db.JSON, nullable=True)

	suggested_inventory_category = db.relationship('InventoryCategory')

	__table_args__ = (
		db.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc'),
	)