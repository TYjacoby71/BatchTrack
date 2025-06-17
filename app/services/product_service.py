
from sqlalchemy import func
from datetime import datetime
from ..models import Product, ProductInventory, ProductEvent, ProductInventoryHistory, Batch, InventoryItem
from ..extensions import db

class ProductService:
    """Service for handling product-related operations"""
    
    @staticmethod
    def create_product(name, description="", category="", tags=None, recipe_id=None):
        """Create a new product"""
        try:
            product = Product(
                name=name,
                description=description,
                category=category,
                tags=tags or [],
                recipe_id=recipe_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(product)
            db.session.commit()
            
            return {"success": True, "product": product, "message": f"Product '{name}' created successfully"}
            
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Error creating product: {str(e)}"}

    @staticmethod
    def create_product_inventory(product_id, variant="", size_label="", quantity=0, unit="", 
                               container_id=None, batch_id=None, cost_per_unit=None):
        """Create product inventory entry"""
        try:
            product_inventory = ProductInventory(
                product_id=product_id,
                variant=variant,
                size_label=size_label,
                quantity=quantity,
                unit=unit,
                container_id=container_id,
                batch_id=batch_id,
                cost_per_unit=cost_per_unit,
                created_at=datetime.utcnow()
            )
            
            db.session.add(product_inventory)
            db.session.commit()
            
            return {"success": True, "product_inventory": product_inventory, 
                   "message": "Product inventory created successfully"}
            
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Error creating product inventory: {str(e)}"}

    @staticmethod
    def adjust_product_inventory(product_inventory_id, quantity_change, reason, notes=""):
        """Adjust product inventory quantity"""
        try:
            product_inventory = ProductInventory.query.get_or_404(product_inventory_id)
            
            # Check if there's enough inventory for negative adjustments
            if quantity_change < 0 and product_inventory.quantity < abs(quantity_change):
                return {
                    "success": False,
                    "message": f"Insufficient inventory. Available: {product_inventory.quantity}, Requested: {abs(quantity_change)}"
                }
            
            # Create history entry
            history_entry = ProductInventoryHistory(
                product_inventory_id=product_inventory_id,
                quantity_change=quantity_change,
                reason=reason,
                notes=notes,
                timestamp=datetime.utcnow()
            )
            
            # Update inventory
            product_inventory.quantity += quantity_change
            product_inventory.last_updated = datetime.utcnow()
            
            db.session.add(history_entry)
            db.session.commit()
            
            return {
                "success": True,
                "message": f"Inventory adjusted by {quantity_change}",
                "new_quantity": product_inventory.quantity,
                "history_entry_id": history_entry.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Error adjusting inventory: {str(e)}"}

    @staticmethod
    def record_product_event(product_id, event_type, description, quantity=None, 
                           product_inventory_id=None, metadata=None):
        """Record a product event"""
        try:
            event = ProductEvent(
                product_id=product_id,
                event_type=event_type,
                description=description,
                quantity=quantity,
                product_inventory_id=product_inventory_id,
                metadata=metadata or {},
                timestamp=datetime.utcnow()
            )
            
            db.session.add(event)
            db.session.commit()
            
            return {"success": True, "event": event, "message": "Event recorded successfully"}
            
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Error recording event: {str(e)}"}

    @staticmethod
    def get_product_inventory_summary(product_id):
        """Get inventory summary for a product"""
        try:
            inventories = ProductInventory.query.filter_by(product_id=product_id).all()
            
            summary = {
                "total_variants": len(set(inv.variant for inv in inventories if inv.variant)),
                "total_quantity": sum(inv.quantity for inv in inventories),
                "variants": {},
                "containers": {}
            }
            
            for inv in inventories:
                # Group by variant
                variant_key = inv.variant or "default"
                if variant_key not in summary["variants"]:
                    summary["variants"][variant_key] = {
                        "total_quantity": 0,
                        "sizes": {},
                        "containers": set()
                    }
                
                summary["variants"][variant_key]["total_quantity"] += inv.quantity
                
                # Group by size within variant
                size_key = inv.size_label or "default"
                if size_key not in summary["variants"][variant_key]["sizes"]:
                    summary["variants"][variant_key]["sizes"][size_key] = 0
                summary["variants"][variant_key]["sizes"][size_key] += inv.quantity
                
                # Track containers
                if inv.container_id:
                    container = InventoryItem.query.get(inv.container_id)
                    if container:
                        summary["variants"][variant_key]["containers"].add(container.name)
                        
                        if container.name not in summary["containers"]:
                            summary["containers"][container.name] = 0
                        summary["containers"][container.name] += inv.quantity
            
            # Convert sets to lists for JSON serialization
            for variant_data in summary["variants"].values():
                variant_data["containers"] = list(variant_data["containers"])
            
            return summary
            
        except Exception as e:
            return {"error": f"Error getting product summary: {str(e)}"}

    @staticmethod
    def get_low_stock_products(threshold=5):
        """Get products with low stock"""
        try:
            low_stock = []
            
            # Get all products with their inventory
            products = Product.query.all()
            
            for product in products:
                total_quantity = db.session.query(
                    func.sum(ProductInventory.quantity)
                ).filter_by(product_id=product.id).scalar() or 0
                
                if total_quantity <= threshold:
                    low_stock.append({
                        "product": product,
                        "total_quantity": total_quantity,
                        "threshold": threshold
                    })
            
            return low_stock
            
        except Exception as e:
            return []

    @staticmethod
    def get_product_history(product_id, limit=50):
        """Get history for a product"""
        try:
            # Get product events
            events = ProductEvent.query.filter_by(
                product_id=product_id
            ).order_by(ProductEvent.timestamp.desc()).limit(limit).all()
            
            # Get inventory history
            inventory_history = db.session.query(ProductInventoryHistory).join(
                ProductInventory
            ).filter(
                ProductInventory.product_id == product_id
            ).order_by(ProductInventoryHistory.timestamp.desc()).limit(limit).all()
            
            return {
                "events": events,
                "inventory_history": inventory_history
            }
            
        except Exception as e:
            return {"events": [], "inventory_history": []}

    @staticmethod
    def get_batch_products(batch_id):
        """Get all product inventories created from a batch"""
        try:
            product_inventories = ProductInventory.query.filter_by(batch_id=batch_id).all()
            
            products = []
            for inv in product_inventories:
                product = Product.query.get(inv.product_id)
                if product:
                    products.append({
                        "product": product,
                        "inventory": inv,
                        "variant": inv.variant,
                        "size_label": inv.size_label,
                        "quantity": inv.quantity,
                        "container": InventoryItem.query.get(inv.container_id) if inv.container_id else None
                    })
            
            return products
            
        except Exception as e:
            return []

    @staticmethod
    def calculate_product_cost(product_inventory_id):
        """Calculate the cost basis for a product inventory"""
        try:
            product_inventory = ProductInventory.query.get(product_inventory_id)
            if not product_inventory:
                return {"error": "Product inventory not found"}
            
            total_cost = 0
            cost_breakdown = []
            
            # If created from a batch, calculate based on ingredient costs
            if product_inventory.batch_id:
                batch = Batch.query.get(product_inventory.batch_id)
                if batch and batch.recipe:
                    # Calculate cost from recipe ingredients
                    for ingredient in batch.recipe.ingredients:
                        ingredient_item = InventoryItem.query.get(ingredient.ingredient_id)
                        if ingredient_item and ingredient_item.average_cost:
                            ingredient_cost = ingredient.quantity * ingredient_item.average_cost
                            total_cost += ingredient_cost
                            cost_breakdown.append({
                                "ingredient": ingredient_item.name,
                                "quantity": ingredient.quantity,
                                "unit_cost": ingredient_item.average_cost,
                                "total_cost": ingredient_cost
                            })
                    
                    # Factor in yield efficiency
                    if batch.final_yield and batch.planned_yield:
                        efficiency = batch.final_yield / batch.planned_yield
                        total_cost = total_cost / efficiency
            
            # Calculate cost per unit
            cost_per_unit = total_cost / product_inventory.quantity if product_inventory.quantity > 0 else 0
            
            return {
                "total_cost": total_cost,
                "cost_per_unit": cost_per_unit,
                "cost_breakdown": cost_breakdown,
                "quantity": product_inventory.quantity
            }
            
        except Exception as e:
            return {"error": f"Error calculating cost: {str(e)}"}

    @staticmethod
    def search_products(query, category=None, tags=None):
        """Search products by name, description, category, or tags"""
        try:
            products_query = Product.query
            
            # Text search
            if query:
                products_query = products_query.filter(
                    db.or_(
                        Product.name.ilike(f"%{query}%"),
                        Product.description.ilike(f"%{query}%")
                    )
                )
            
            # Category filter
            if category:
                products_query = products_query.filter(Product.category == category)
            
            # Tags filter
            if tags:
                for tag in tags:
                    products_query = products_query.filter(Product.tags.contains([tag]))
            
            products = products_query.all()
            
            # Add inventory summary to each product
            results = []
            for product in products:
                summary = ProductService.get_product_inventory_summary(product.id)
                results.append({
                    "product": product,
                    "inventory_summary": summary
                })
            
            return results
            
        except Exception as e:
            return []
