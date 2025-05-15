
from models import Batch, ProductInventory, db
from sqlalchemy import and_

class FIFOService:
    @staticmethod
    def deduct_intermediate_fifo(ingredient_name, unit, quantity_requested):
        """
        Deducts intermediate ingredients using FIFO logic.
        Returns (success, list of (batch_id, quantity_deducted) pairs)
        """
        remaining = quantity_requested
        used_batches = []

        batches = Batch.query.filter(
            and_(
                Batch.recipe.has(name=ingredient_name),
                Batch.status == 'completed',
                Batch.batch_type == 'ingredient',
                Batch.final_quantity > 0
            )
        ).order_by(Batch.completed_at.asc()).all()

        for batch in batches:
            if remaining <= 0:
                break

            deduction = min(batch.final_quantity, remaining)
            batch.final_quantity -= deduction
            remaining -= deduction
            used_batches.append((batch.id, deduction))

        if remaining > 0:
            return False, []

        db.session.commit()
        return True, used_batches

    @staticmethod
    def deduct_product_fifo(product_id, variant, unit, quantity_requested):
        """
        Deducts product inventory using FIFO logic.
        Returns (success, list of (inventory_id, quantity_deducted) pairs)
        """
        remaining = quantity_requested
        used_inventory = []

        inventory_rows = ProductInventory.query.filter(
            and_(
                ProductInventory.product_id == product_id,
                ProductInventory.variant == variant,
                ProductInventory.unit == unit,
                ProductInventory.quantity > 0
            )
        ).order_by(ProductInventory.timestamp.asc()).all()

        for row in inventory_rows:
            if remaining <= 0:
                break

            deduction = min(row.quantity, remaining)
            row.quantity -= deduction
            remaining -= deduction
            used_inventory.append((row.id, deduction))

        if remaining > 0:
            return False, []

        db.session.commit()
        return True, used_inventory

    @staticmethod
    def get_fifo_batches(ingredient_name=None, product_id=None):
        """Gets all available batches ordered by date."""
        if ingredient_name:
            return Batch.query.filter(
                and_(
                    Batch.recipe.has(name=ingredient_name),
                    Batch.status == 'completed',
                    Batch.batch_type == 'ingredient',
                    Batch.final_quantity > 0
                )
            ).order_by(Batch.completed_at.asc()).all()
        elif product_id:
            return ProductInventory.query.filter(
                and_(
                    ProductInventory.product_id == product_id,
                    ProductInventory.quantity > 0
                )
            ).order_by(ProductInventory.timestamp.asc()).all()
        return []
