from __future__ import annotations

import logging

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import GlobalItem, InventoryItem, Unit

from .. import recipes_bp

logger = logging.getLogger(__name__)


@recipes_bp.route('/units/quick-add', methods=['POST'])
@login_required
def quick_add_unit():
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        unit_type = (data.get('type') or data.get('unit_type') or 'count').strip()

        if not name:
            return jsonify({'error': 'Unit name is required'}), 400

        if unit_type != 'count':
            unit_type = 'count'

        existing = Unit.query.filter(
            func.lower(Unit.name) == func.lower(db.literal(name)),
            ((Unit.is_custom == False) | (Unit.organization_id == current_user.organization_id)),
        ).first()
        if existing:
            return jsonify(
                {
                    'id': existing.id,
                    'name': existing.name,
                    'unit_type': existing.unit_type,
                    'symbol': existing.symbol,
                    'is_custom': existing.is_custom,
                }
            )

        unit = Unit(
            name=name,
            unit_type=unit_type,
            base_unit='count',
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        db.session.add(unit)
        db.session.commit()
        return jsonify(
            {
                'id': unit.id,
                'name': unit.name,
                'unit_type': unit.unit_type,
                'symbol': unit.symbol,
                'is_custom': True,
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@recipes_bp.route('/ingredients/quick-add', methods=['POST'])
@login_required
def quick_add_ingredient():
    try:
        data = request.get_json()
        name = data.get('name')
        unit = data.get('unit', 'each')
        ingredient_type = data.get('type', 'ingredient')

        if not name:
            return jsonify({'error': 'Ingredient name is required'}), 400

        existing = InventoryItem.query.filter_by(
            name=name,
            organization_id=current_user.organization_id,
        ).first()

        if existing:
            return jsonify(
                {
                    'id': existing.id,
                    'name': existing.name,
                    'unit': existing.unit,
                    'type': existing.type,
                    'exists': True,
                }
            )

        ingredient = InventoryItem(
            name=name,
            unit=unit,
            type=ingredient_type,
            quantity=0.0,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )

        db.session.add(ingredient)
        db.session.commit()

        logger.info("Quick-added ingredient: %s (ID: %s)", name, ingredient.id)

        return jsonify(
            {
                'id': ingredient.id,
                'name': ingredient.name,
                'unit': ingredient.unit,
                'type': ingredient.type,
                'exists': False,
            }
        )

    except Exception as exc:
        db.session.rollback()
        logger.error("Error quick-adding ingredient: %s", exc)
        return jsonify({'error': str(exc)}), 500


@recipes_bp.route('/inventory/check-new-items', methods=['POST'])
@login_required
def check_new_inventory_items():
    """Identify inventory names that do not exist in the org or global library."""
    try:
        data = request.get_json() or {}
        items = data.get('items') or []
        missing = []
        seen = set()

        for item in items:
            name = (item.get('name') or '').strip()
            item_type = (item.get('item_type') or 'ingredient').strip().lower() or 'ingredient'
            if not name:
                continue
            key = (item_type, name.lower())
            if key in seen:
                continue
            seen.add(key)

            inv_query = InventoryItem.query.filter(
                func.lower(InventoryItem.name) == func.lower(db.literal(name)),
                InventoryItem.type == item_type,
            )
            if current_user.organization_id:
                inv_query = inv_query.filter(
                    InventoryItem.organization_id == current_user.organization_id
                )
            else:
                inv_query = inv_query.filter(InventoryItem.organization_id.is_(None))

            inv_exists = inv_query.first()

            global_exists = (
                GlobalItem.query.filter(
                    func.lower(GlobalItem.name) == func.lower(db.literal(name)),
                    GlobalItem.item_type == item_type,
                    GlobalItem.is_archived != True,
                )
                .order_by(GlobalItem.id.asc())
                .first()
            )

            if not inv_exists and not global_exists:
                missing.append({'name': name, 'item_type': item_type})

        return jsonify({'missing': missing})
    except Exception as exc:
        logger.exception("Error checking new inventory items: %s", exc)
        return jsonify({'missing': [], 'error': 'Unable to validate inventory names'}), 500
