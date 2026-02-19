from __future__ import annotations

import logging

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import InventoryItem, Unit
from app.utils.permissions import require_permission

from .. import recipes_bp

logger = logging.getLogger(__name__)


@recipes_bp.route("/units/quick-add", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def quick_add_unit():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        unit_type = (data.get("type") or data.get("unit_type") or "count").strip()

        if not name:
            return jsonify({"error": "Unit name is required"}), 400

        if unit_type != "count":
            unit_type = "count"

        existing = Unit.query.filter(
            func.lower(Unit.name) == func.lower(db.literal(name)),
            (
                (Unit.is_custom.is_(False))
                | (Unit.organization_id == current_user.organization_id)
            ),
        ).first()
        if existing:
            return jsonify(
                {
                    "id": existing.id,
                    "name": existing.name,
                    "unit_type": existing.unit_type,
                    "symbol": existing.symbol,
                    "is_custom": existing.is_custom,
                }
            )

        unit = Unit(
            name=name,
            unit_type=unit_type,
            base_unit="count",
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
                "id": unit.id,
                "name": unit.name,
                "unit_type": unit.unit_type,
                "symbol": unit.symbol,
                "is_custom": True,
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@recipes_bp.route("/ingredients/quick-add", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def quick_add_ingredient():
    try:
        data = request.get_json()
        name = data.get("name")
        unit = data.get("unit", "each")
        ingredient_type = data.get("type", "ingredient")

        if not name:
            return jsonify({"error": "Ingredient name is required"}), 400

        existing = InventoryItem.query.filter_by(
            name=name,
            organization_id=current_user.organization_id,
        ).first()

        if existing:
            return jsonify(
                {
                    "id": existing.id,
                    "name": existing.name,
                    "unit": existing.unit,
                    "type": existing.type,
                    "exists": True,
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
                "id": ingredient.id,
                "name": ingredient.name,
                "unit": ingredient.unit,
                "type": ingredient.type,
                "exists": False,
            }
        )

    except Exception as exc:
        db.session.rollback()
        logger.error("Error quick-adding ingredient: %s", exc)
        return jsonify({"error": str(exc)}), 500
