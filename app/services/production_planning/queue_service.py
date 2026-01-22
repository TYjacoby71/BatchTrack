from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask_login import current_user

from app.extensions import db
from app.models import (
    Batch,
    BatchContainer,
    BatchConsumable,
    BatchIngredient,
    InventoryItem,
    Recipe,
    UnifiedInventoryHistory,
)
from app.models.batch_queue import BatchQueueItem
from app.models.inventory_lot import InventoryLot
from app.services.costing_engine import weighted_unit_cost_for_batch_item
from app.services.inventory_adjustment import process_inventory_adjustment
from app.services.production_planning.service import PlanProductionService
from app.services.stock_check.core import UniversalStockCheckService
from app.services.unit_conversion import ConversionEngine
from app.utils.code_generator import generate_batch_label_code
from app.utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


class BatchQueueService:
    @staticmethod
    def _queue_tag(queue_item: BatchQueueItem) -> str:
        return f"[QUEUE:{queue_item.id}|CODE:{queue_item.queue_code}]"

    @staticmethod
    def _queue_note(queue_item: BatchQueueItem, recipe: Recipe) -> str:
        return f"{BatchQueueService._queue_tag(queue_item)} Planned batch {queue_item.queue_code} for {recipe.name}"

    @staticmethod
    def _today_bounds() -> tuple[datetime, datetime]:
        now = TimezoneUtils.utc_now()
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return start, end

    @classmethod
    def expire_stale_queue_items(cls, organization_id: int):
        start, _ = cls._today_bounds()
        stale_items = BatchQueueItem.query.filter(
            BatchQueueItem.organization_id == organization_id,
            BatchQueueItem.status == 'queued',
            BatchQueueItem.created_at < start,
        ).all()
        if not stale_items:
            return 0
        expired = 0
        for item in stale_items:
            ok, _ = cls.cancel_queue_item(item, defer_commit=True)
            if ok:
                expired += 1
        db.session.commit()
        return expired

    @classmethod
    def enqueue_batch(cls, recipe_id: int, scale: float, batch_type: str, notes: str, containers: list | None):
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return None, "Recipe not found"

        org_id = current_user.organization_id
        cls.expire_stale_queue_items(org_id)

        if scale <= 0:
            return None, "Scale must be greater than zero"

        plan_snapshot = PlanProductionService.build_plan(
            recipe=recipe,
            scale=scale,
            batch_type=batch_type,
            notes=notes,
            containers=containers,
        )
        plan_dict = plan_snapshot.to_dict()

        start, end = cls._today_bounds()
        queue_position = (
            BatchQueueItem.query.filter(
                BatchQueueItem.organization_id == org_id,
                BatchQueueItem.created_at >= start,
                BatchQueueItem.created_at < end,
            ).count()
            + 1
        )
        queue_code = f"PLN-{queue_position:03d}"

        queue_item = BatchQueueItem(
            recipe_id=recipe.id,
            queue_code=queue_code,
            queue_position=queue_position,
            scale=scale,
            batch_type=batch_type or 'ingredient',
            projected_yield=plan_dict.get('projected_yield'),
            projected_yield_unit=plan_dict.get('projected_yield_unit'),
            notes=notes,
            plan_snapshot=plan_dict,
            status='queued',
            created_by=current_user.id if current_user.is_authenticated else None,
            organization_id=org_id,
        )
        db.session.add(queue_item)
        db.session.flush()

        queue_note = cls._queue_note(queue_item, recipe)
        success, error = cls._reserve_plan_inventory(queue_item, recipe, plan_dict, queue_note)
        if not success:
            db.session.rollback()
            return None, error

        db.session.commit()
        return queue_item, None

    @classmethod
    def _reserve_plan_inventory(cls, queue_item: BatchQueueItem, recipe: Recipe, plan_dict: dict, queue_note: str):
        errors = []

        ingredients = plan_dict.get('ingredients_plan', []) or []
        for line in ingredients:
            item = db.session.get(InventoryItem, line.get('inventory_item_id'))
            if not item:
                continue
            required_amount = float(line.get('quantity') or 0.0)
            if required_amount <= 0:
                continue
            required_unit = line.get('unit') or item.unit
            try:
                conversion_result = ConversionEngine.convert_units(
                    required_amount,
                    required_unit,
                    item.unit,
                    ingredient_id=item.id,
                    density=item.density or (item.category.default_density if item.category else None),
                )
                required_converted = conversion_result['converted_value']
            except Exception as e:
                errors.append(f"Conversion failed for {item.name}: {e}")
                continue

            success, message = process_inventory_adjustment(
                item_id=item.id,
                change_type='planned',
                quantity=required_converted,
                unit=item.unit,
                notes=queue_note,
                created_by=current_user.id,
                defer_commit=True,
            )
            if not success:
                return False, message or f"Not enough {item.name} in stock."

        consumables = plan_dict.get('consumables_plan', []) or []
        for line in consumables:
            item = db.session.get(InventoryItem, line.get('inventory_item_id'))
            if not item:
                continue
            required_amount = float(line.get('quantity') or 0.0)
            if required_amount <= 0:
                continue
            required_unit = line.get('unit') or item.unit
            try:
                conversion_result = ConversionEngine.convert_units(
                    required_amount,
                    required_unit,
                    item.unit,
                    ingredient_id=item.id,
                    density=item.density or (item.category.default_density if item.category else None),
                )
                required_converted = conversion_result['converted_value']
            except Exception as e:
                errors.append(f"Conversion failed for {item.name}: {e}")
                continue

            success, message = process_inventory_adjustment(
                item_id=item.id,
                change_type='planned',
                quantity=required_converted,
                unit=item.unit,
                notes=queue_note,
                created_by=current_user.id,
                defer_commit=True,
            )
            if not success:
                return False, message or f"Not enough {item.name} in stock."

        containers = plan_dict.get('containers', []) or []
        for selection in containers:
            container_id = selection.get('id')
            quantity = float(selection.get('quantity') or 0.0)
            if not container_id or quantity <= 0:
                continue
            container_item = db.session.get(InventoryItem, container_id)
            if not container_item:
                continue
            container_unit = container_item.unit or 'count'
            success, message = process_inventory_adjustment(
                item_id=container_item.id,
                change_type='planned',
                quantity=quantity,
                unit=container_unit,
                notes=queue_note,
                created_by=current_user.id,
                defer_commit=True,
            )
            if not success:
                return False, message or f"Not enough {container_item.name} in stock."

        if errors:
            return False, "; ".join(errors)
        return True, None

    @classmethod
    def cancel_queue_item(cls, queue_item: BatchQueueItem, defer_commit: bool = False):
        if not queue_item or queue_item.status != 'queued':
            return False, "Queue item is not active."

        tag = cls._queue_tag(queue_item)
        planned_entries = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.organization_id == queue_item.organization_id,
            UnifiedInventoryHistory.change_type == 'planned',
            UnifiedInventoryHistory.notes.ilike(f"%{tag}%"),
        ).all()

        for entry in planned_entries:
            qty = abs(float(entry.quantity_change or 0.0))
            if qty <= 0:
                db.session.delete(entry)
                continue
            lot = db.session.get(InventoryLot, entry.affected_lot_id) if entry.affected_lot_id else None
            if lot:
                credited = lot.credit_back(qty)
                if not credited:
                    lot.remaining_quantity = float(lot.remaining_quantity or 0.0) + qty
                item = db.session.get(InventoryItem, lot.inventory_item_id)
                if item:
                    item.quantity = float(item.quantity or 0.0) + qty
            db.session.delete(entry)

        queue_item.status = 'cancelled'
        queue_item.cancelled_at = TimezoneUtils.utc_now()

        if not defer_commit:
            db.session.commit()
        return True, "Queue item cancelled."

    @classmethod
    def start_queue_item(cls, queue_item: BatchQueueItem):
        if not queue_item or queue_item.status != 'queued':
            return None, "Queue item is not active."

        recipe = db.session.get(Recipe, queue_item.recipe_id)
        if not recipe:
            return None, "Recipe not found"

        plan_snapshot = queue_item.plan_snapshot or {}
        portioning = plan_snapshot.get('portioning') or {}
        projected_yield = float(plan_snapshot.get('projected_yield') or 0.0)
        projected_yield_unit = plan_snapshot.get('projected_yield_unit') or ''

        label_code = generate_batch_label_code(recipe)
        batch = Batch(
            recipe_id=queue_item.recipe_id,
            label_code=label_code,
            batch_type=plan_snapshot.get('batch_type') or queue_item.batch_type or 'ingredient',
            projected_yield=projected_yield,
            projected_yield_unit=projected_yield_unit,
            scale=float(plan_snapshot.get('scale') or queue_item.scale or 1.0),
            status='in_progress',
            notes=plan_snapshot.get('notes') or queue_item.notes or '',
            is_portioned=bool(portioning.get('is_portioned')) if portioning else False,
            portion_name=portioning.get('portion_name') if portioning else None,
            projected_portions=int(portioning.get('portion_count')) if portioning and portioning.get('portion_count') is not None else None,
            portion_unit_id=portioning.get('portion_unit_id') if portioning else None,
            plan_snapshot=plan_snapshot,
            created_by=(getattr(current_user, 'id', None) or getattr(recipe, 'created_by', None) or 1),
            organization_id=(getattr(current_user, 'organization_id', None) or getattr(recipe, 'organization_id', None) or 1),
            started_at=TimezoneUtils.utc_now(),
        )
        db.session.add(batch)
        db.session.flush()

        # Lock costing method for this batch based on org setting
        try:
            if hasattr(batch, 'cost_method'):
                org = getattr(current_user, 'organization', None)
                method = (getattr(org, 'inventory_cost_method', None) or 'fifo') if org else 'fifo'
                method = method if method in ('fifo', 'average') else 'fifo'
                batch.cost_method = method
                if hasattr(batch, 'cost_method_locked_at'):
                    batch.cost_method_locked_at = TimezoneUtils.utc_now()
        except Exception:
            try:
                if hasattr(batch, 'cost_method'):
                    batch.cost_method = 'fifo'
            except Exception:
                pass

        tag = cls._queue_tag(queue_item)
        planned_entries = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.organization_id == queue_item.organization_id,
            UnifiedInventoryHistory.change_type == 'planned',
            UnifiedInventoryHistory.notes.ilike(f"%{tag}%"),
        ).all()
        if not planned_entries:
            return None, "No reserved inventory found for this queue item."

        reserved_quantities = {}
        for entry in planned_entries:
            entry.change_type = 'batch'
            entry.batch_id = batch.id
            entry.fifo_code = batch.label_code
            qty = abs(float(entry.quantity_change or 0.0))
            if qty <= 0:
                continue
            info = reserved_quantities.setdefault(entry.inventory_item_id, {"quantity": 0.0, "unit": entry.unit})
            info["quantity"] += qty

        ingredient_ids = {line.get('inventory_item_id') for line in plan_snapshot.get('ingredients_plan', []) or []}
        consumable_ids = {line.get('inventory_item_id') for line in plan_snapshot.get('consumables_plan', []) or []}
        container_selections = plan_snapshot.get('containers', []) or []

        for item_id in ingredient_ids:
            info = reserved_quantities.get(item_id)
            if not info:
                continue
            item = db.session.get(InventoryItem, item_id)
            if not item:
                continue
            try:
                cost_per_unit_snapshot = weighted_unit_cost_for_batch_item(item_id, batch.id)
            except Exception:
                cost_per_unit_snapshot = float(item.cost_per_unit or 0.0)

            db.session.add(
                BatchIngredient(
                    batch_id=batch.id,
                    inventory_item_id=item_id,
                    quantity_used=info["quantity"],
                    unit=info["unit"] or item.unit,
                    cost_per_unit=cost_per_unit_snapshot,
                    organization_id=current_user.organization_id,
                )
            )

        for item_id in consumable_ids:
            info = reserved_quantities.get(item_id)
            if not info:
                continue
            item = db.session.get(InventoryItem, item_id)
            if not item:
                continue
            try:
                cost_per_unit_snapshot = weighted_unit_cost_for_batch_item(item_id, batch.id)
            except Exception:
                cost_per_unit_snapshot = float(item.cost_per_unit or 0.0)

            db.session.add(
                BatchConsumable(
                    batch_id=batch.id,
                    inventory_item_id=item_id,
                    quantity_used=info["quantity"],
                    unit=info["unit"] or item.unit,
                    cost_per_unit=cost_per_unit_snapshot,
                    organization_id=current_user.organization_id,
                )
            )

        for selection in container_selections:
            container_id = selection.get('id')
            quantity = int(selection.get('quantity') or 0)
            if not container_id or quantity <= 0:
                continue
            container_item = db.session.get(InventoryItem, container_id)
            if not container_item:
                continue
            try:
                cost_each = weighted_unit_cost_for_batch_item(container_id, batch.id)
            except Exception:
                cost_each = float(container_item.cost_per_unit or 0.0)

            db.session.add(
                BatchContainer(
                    batch_id=batch.id,
                    container_id=container_id,
                    container_quantity=quantity,
                    quantity_used=quantity,
                    cost_each=cost_each,
                    organization_id=current_user.organization_id,
                )
            )

        queue_item.status = 'started'
        queue_item.started_at = TimezoneUtils.utc_now()
        queue_item.batch_id = batch.id

        db.session.commit()
        return batch, None

    @classmethod
    def verify_queue_stock(cls, recipe_id: int, scale: float):
        uscs = UniversalStockCheckService()
        result = uscs.check_recipe_stock(recipe_id, scale)
        if not result.get('success'):
            return False, result.get('error') or 'Unable to verify inventory for this recipe.'

        stock_issues = []
        for item in result.get('stock_check', []) or []:
            needed = float(item.get('needed_quantity') or item.get('needed_amount') or 0)
            available = float(item.get('available_quantity') or 0)
            status = (item.get('status') or '').upper()
            if status in {'NEEDED', 'OUT_OF_STOCK', 'ERROR', 'DENSITY_MISSING'} or available < needed:
                stock_issues.append({
                    'item_id': item.get('item_id'),
                    'name': item.get('item_name'),
                    'needed_quantity': needed,
                    'available_quantity': available,
                    'needed_unit': item.get('needed_unit'),
                    'available_unit': item.get('available_unit'),
                    'status': status or ('LOW' if available < needed else 'UNKNOWN'),
                })

        if stock_issues:
            return False, "Insufficient inventory for one or more items."
        return True, None
