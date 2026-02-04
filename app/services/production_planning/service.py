from typing import Optional
from .types import PlanSnapshot, PortioningPlan, IngredientLine, ConsumableLine, ContainerSelection
from app.services.lineage_service import generate_lineage_id


class PlanProductionService:
    @staticmethod
    def build_plan(recipe, scale: float, batch_type: str, notes: str = '', containers: Optional[list] = None) -> PlanSnapshot:
        """Build a fully frozen plan snapshot from a recipe and scale. No client overrides."""
        containers = containers or []

        # Projected yield snapshot
        projected_yield = float((recipe.predicted_yield or 0.0) * float(scale or 1.0))
        projected_yield_unit = recipe.predicted_yield_unit or ''

        # Portioning snapshot strictly from recipe additive columns (no overrides)
        portioning = PortioningPlan(is_portioned=False, portion_name=None, portion_unit_id=None, portion_count=None)
        try:
            if getattr(recipe, 'is_portioned', False):
                portioning = PortioningPlan(
                    is_portioned=True,
                    portion_name=getattr(recipe, 'portion_name', None),
                    portion_unit_id=None,
                    portion_count=getattr(recipe, 'portion_count', None)
                )
        except Exception:
            portioning = PortioningPlan(is_portioned=False, portion_name=None, portion_unit_id=None, portion_count=None)

        # Ingredients plan (scale recipe_ingredients)
        ingredients_plan = []
        for assoc in getattr(recipe, 'recipe_ingredients', []) or []:
            try:
                ingredients_plan.append(
                    IngredientLine(
                        inventory_item_id=assoc.inventory_item_id,
                        quantity=float(assoc.quantity or 0.0) * float(scale or 1.0),
                        unit=str(assoc.unit or '')
                    )
                )
            except Exception:
                continue

        # Consumables plan (scale recipe_consumables)
        consumables_plan = []
        for assoc in getattr(recipe, 'recipe_consumables', []) or []:
            try:
                consumables_plan.append(
                    ConsumableLine(
                        inventory_item_id=assoc.inventory_item_id,
                        quantity=float(assoc.quantity or 0.0) * float(scale or 1.0),
                        unit=str(assoc.unit or '')
                    )
                )
            except Exception:
                continue

        # Containers snapshot - pass-through of selections
        container_selection = []
        for c in containers:
            try:
                container_selection.append(ContainerSelection(id=int(c['id']), quantity=int(c['quantity'])))
            except Exception:
                continue

        # Attach category-specific structured data (nullable) for full audit/export
        try:
            category_extension = dict(getattr(recipe, 'category_data', None) or {})
        except Exception:
            category_extension = None

        return PlanSnapshot(
            recipe_id=recipe.id,
            target_version_id=recipe.id,
            lineage_snapshot=generate_lineage_id(recipe),
            scale=float(scale or 1.0),
            batch_type=batch_type or 'ingredient',
            notes=notes or '',
            projected_yield=projected_yield,
            projected_yield_unit=projected_yield_unit,
            portioning=portioning,
            ingredients_plan=ingredients_plan,
            consumables_plan=consumables_plan,
            containers=container_selection,
            requires_containers=bool(len(container_selection) > 0),
            category_extension=category_extension
        )