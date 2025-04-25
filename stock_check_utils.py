
from models import InventoryItem, RecipeIngredient
from services.unit_conversion import ConversionEngine
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

def get_available_containers():
    """Get all available containers ordered by name"""
    return InventoryItem.query.filter_by(type='container').order_by(InventoryItem.name).all()

def check_stock_for_recipe(recipe, scale=1.0):
    if not recipe:
        logger.error("Null recipe passed to check_stock_for_recipe")
        raise ValueError("Recipe cannot be null")
        
    if scale <= 0:
        logger.error(f"Invalid scale value: {scale}")
        raise ValueError("Scale must be greater than 0")

    results = []
    all_ok = True

    try:
        for assoc in recipe.recipe_ingredients:
            ing = assoc.inventory_item
            if not ing:
                logger.warning(f"Missing inventory item for recipe {recipe.id}")
                continue

            needed = assoc.amount * scale
            try:
                needed_converted = ConversionEngine.convert_units(needed, assoc.unit, ing.unit)
                logger.debug(f"Converted {needed} {assoc.unit} to {needed_converted} {ing.unit}")
            except Exception as e:
                logger.error(f"Unit conversion failed for {ing.name}: {str(e)}")
                needed_converted = needed
                
            try:
                available = ing.quantity
            except SQLAlchemyError as e:
                logger.error(f"Failed to get quantity for {ing.name}: {str(e)}")
                available = 0

            status = 'OK' if available >= needed_converted else 'LOW' if available > 0 else 'NEEDED'
            if status != 'OK':
                all_ok = False
                logger.info(f"Stock check failed for {ing.name}: needs {needed_converted}, has {available}")
            
            results.append({
                'name': ing.name,
                'unit': ing.unit,
                'needed': round(needed_converted, 2),
                'available': round(available, 2),
                'status': status
            })

        return results, all_ok
        
    except Exception as e:
        logger.exception(f"Stock check failed for recipe {recipe.id}")
        raise

def check_container_availability(container_ids, scale=1.0):
    results = []
    all_ok = True
    
    from models import InventoryItem

    for cid in container_ids:
        container = InventoryItem.query.get(cid)
        if not container or container.type != 'container':
            continue

        required = 1 * scale  # assume 1 per unit for now
        available = container.quantity
        unit = container.unit

        if available >= required:
            status = 'OK'
        elif available > 0:
            status = 'LOW'
            all_ok = False
        else:
            status = 'NEEDED'
            all_ok = False

        results.append({
            'name': container.name,
            'unit': unit,
            'needed': required,
            'available': available,
            'status': status,
            'type': 'container'
        })

    return results, all_ok
