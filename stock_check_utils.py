from models import InventoryItem, RecipeIngredient
from services.unit_conversion_service import UnitConversionService
import logging

logger = logging.getLogger(__name__)

class StockCheckResult:
    def __init__(self, name, unit, needed, available, item_type='ingredient'):
        self.name = name
        self.unit = unit
        self.needed = round(float(needed), 2)
        self.available = round(float(available), 2)
        self.type = item_type
        self.status = self._calculate_status()

    def _calculate_status(self):
        if self.available >= self.needed:
            return 'OK'
        elif self.available > 0:
            return 'LOW'
        return 'NEEDED'

    def to_dict(self):
        return {
            'name': self.name,
            'unit': self.unit,
            'needed': self.needed,
            'available': self.available,
            'status': self.status,
            'type': self.type
        }

def check_recipe_stock(recipe, scale=1.0):
    if not recipe:
        logger.error("Null recipe passed to check_recipe_stock")
        raise ValueError("Recipe cannot be null")
        
    logger.debug(f"Checking stock for recipe {recipe.id} at scale {scale}")

    if scale <= 0:
        logger.error(f"Invalid scale value: {scale}")
        raise ValueError("Scale must be greater than 0")

    results = []
    conversion_issues = False

    for ingredient in recipe.recipe_ingredients:
        if not ingredient.inventory_item:
            logger.warning(f"Missing inventory item in recipe {recipe.id}")
            continue

        try:
            needed = ingredient.amount * scale
            needed_converted = UnitConversionService.convert(
                needed, 
                ingredient.unit,
                ingredient.inventory_item.unit
            )[0]

            results.append(StockCheckResult(
                name=ingredient.inventory_item.name,
                unit=ingredient.inventory_item.unit,
                needed=needed_converted,
                available=ingredient.inventory_item.quantity
            ))

        except Exception as e:
            logger.error(f"Stock check failed for {ingredient.inventory_item.name}: {str(e)}")
            conversion_issues = True
            continue

    return [r.to_dict() for r in results], conversion_issues

def check_containers(container_ids, scale=1.0):
    if not container_ids:
        return [], True

    results = []
    all_ok = True

    for container_id in container_ids:
        container = InventoryItem.query.get(container_id)
        if not container or container.type != 'container':
            continue

        needed = scale
        result = StockCheckResult(
            name=container.name,
            unit=container.unit,
            needed=needed,
            available=container.quantity,
            item_type='container'
        )

        if result.status != 'OK':
            all_ok = False

        results.append(result.to_dict())

    return results, all_ok

def get_available_containers():
    """Get all available containers ordered by name"""
    return InventoryItem.query.filter_by(type='container').order_by(InventoryItem.name).all()