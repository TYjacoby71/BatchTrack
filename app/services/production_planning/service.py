from typing import Optional
from .types import PlanSnapshot, PortioningPlan, IngredientLine, ConsumableLine, ContainerSelection


class PlanProductionService:
    @staticmethod
    def build_plan(recipe, scale: float, batch_type: str, notes: str = '', containers: Optional[list] = None, portioning_override: Optional[dict] = None) -> PlanSnapshot:
        """Build a fully frozen plan snapshot from a recipe and scale."""
        containers = containers or []

        # Projected yield snapshot
        projected_yield = float((recipe.predicted_yield or 0.0) * float(scale or 1.0))
        projected_yield_unit = recipe.predicted_yield_unit or ''

        # Portioning snapshot: override from request wins; else from recipe additive columns
        portioning = PortioningPlan(is_portioned=False, portion_name=None, portion_unit_id=None, portion_count=None)
        if portioning_override and isinstance(portioning_override, dict) and portioning_override.get('is_portioned'):
            pc = portioning_override.get('portion_count')
            portioning = PortioningPlan(
                is_portioned=True,
                portion_name=portioning_override.get('portion_name'),
                portion_unit_id=portioning_override.get('portion_unit_id'),
                portion_count=(int(pc) if pc is not None else None)
            )
        else:
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

        return PlanSnapshot(
            recipe_id=recipe.id,
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
            category_extension=None
        )

