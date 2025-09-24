
from flask_login import current_user
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class Recipe(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    label_prefix = db.Column(db.String(8))
    qr_image = db.Column(db.String(128))
    parent_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=True)
    is_locked = db.Column(db.Boolean, default=False)
    predicted_yield = db.Column(db.Float, default=0.0)
    predicted_yield_unit = db.Column(db.String(50), default="oz")
    allowed_containers = db.Column(db.PickleType, default=list)
    category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_category = db.relationship('ProductCategory')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # Timestamps for retention calculations
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    updated_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, onupdate=TimezoneUtils.utc_now)
    parent = db.relationship('Recipe', remote_side=[id], backref='variations')
    recipe_ingredients = db.relationship('RecipeIngredient', backref='recipe', cascade="all, delete-orphan")
    # Consumables used during production (e.g., gloves, filters). Snapshot at batch start.
    recipe_consumables = db.relationship('RecipeConsumable', backref='recipe', cascade="all, delete-orphan")
    portioning_data = db.Column(db.JSON, nullable=True)

    def get_portioned_snapshot(self, scale: float = 1.0):
        """Return a clean, projected portioning snapshot for a given scale.

        The snapshot is ready to be stored on a Batch as the source of truth.
        """
        data = getattr(self, 'portioning_data', None)
        if not data or not data.get('is_portioned'):
            return None

        try:
            base_portion_count = int(data.get('portion_count') or 0)
            portion_name = data.get('portion_name')
            bulk_yield_quantity = float(data.get('bulk_yield_quantity') or (self.predicted_yield or 0))
            bulk_yield_unit = data.get('bulk_yield_unit') or self.predicted_yield_unit

            projected_portions = int(round(base_portion_count * float(scale))) if base_portion_count > 0 else None
            derivative_weight = None
            if projected_portions and projected_portions > 0:
                derivative_weight = (bulk_yield_quantity * float(scale)) / float(projected_portions)

            snapshot = {
                'is_portioned': True,
                'portion_name': portion_name,
                'portion_count': base_portion_count,
                'projected_portions': projected_portions,
                'derivative_weight': round(derivative_weight, 3) if isinstance(derivative_weight, (int, float)) else None,
                'bulk_yield_quantity': bulk_yield_quantity * float(scale),
                'bulk_yield_unit': bulk_yield_unit,
            }
            return snapshot
        except (ValueError, TypeError):
            return None

class RecipeIngredient(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_ingredient'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)

    inventory_item = db.relationship('InventoryItem', backref='recipe_usages')


class RecipeConsumable(ScopedModelMixin, db.Model):
    __tablename__ = 'recipe_consumable'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(32), nullable=False)
    notes = db.Column(db.Text)
    order_position = db.Column(db.Integer, default=0)

    inventory_item = db.relationship('InventoryItem', backref='recipe_consumable_usages')
