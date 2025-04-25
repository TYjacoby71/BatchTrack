from models import InventoryItem, RecipeIngredient
from services.unit_conversion_service import UnitConversionService as ConversionService
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
    conversion_issues = False

    from models import InventoryItem

    try:
        for assoc in recipe.recipe_ingredients:
            ing = assoc.inventory_item
            if not ing:
                logger.warning(f"Missing inventory item for recipe {recipe.id}")
                continue

            needed = assoc.amount * scale
            try:
                needed_converted = ConversionService.convert(needed, assoc.unit, ing.unit)[0]
                logger.debug(f"Converted {needed} {assoc.unit} to {needed_converted} {ing.unit}")
            except Exception as e:
                logger.warning(f"Unit conversion failed for {ing.name}: {str(e)}")
                needed_converted = needed
                conversion_issues = True

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

        return results, all_ok, conversion_issues

    except Exception as e:
        logger.exception(f"Stock check failed for recipe {recipe.id}")
        raise

def check_container_availability(container_ids, scale=1.0):
    if not container_ids:
        logger.warning("Empty container list passed to check_container_availability")
        return [], True

    if scale <= 0:
        logger.error(f"Invalid container scale value: {scale}")
        raise ValueError("Container scale must be greater than 0")

    results = []
    all_ok = True

    from models import InventoryItem

    try:
        for cid in container_ids:
            try:
                container = InventoryItem.query.get(cid)
                if not container:
                    logger.warning(f"Container ID {cid} not found")
                    continue

                if container.type != 'container':
                    logger.warning(f"Item {cid} is not a container type")
                    continue

                try:
                    required = 1 * scale  # assume 1 per unit for now
                    available = container.quantity
                    unit = container.unit

                    if available >= required:
                        status = 'OK'
                    elif available > 0:
                        status = 'LOW'
                        all_ok = False
                        logger.info(f"Container {container.name} low: needs {required}, has {available}")
                    else:
                        status = 'NEEDED'
                        all_ok = False
                        logger.info(f"Container {container.name} needed: requires {required}, has none")

                    results.append({
                        'name': container.name,
                        'unit': unit,
                        'needed': round(required, 2),
                        'available': round(available, 2),
                        'status': status,
                        'type': 'container'
                    })
                except (TypeError, ValueError) as e:
                    logger.error(f"Error processing container {cid}: {str(e)}")
                    continue

            except SQLAlchemyError as e:
                logger.error(f"Database error fetching container {cid}: {str(e)}")
                continue

        return results, all_ok

    except Exception as e:
        logger.exception("Container availability check failed")
        raise