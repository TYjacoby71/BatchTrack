from __future__ import annotations

import logging

from flask import jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import InventoryItem
from app.utils.permissions import require_permission

from .. import recipes_bp

logger = logging.getLogger(__name__)


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

        existing = (
            InventoryItem.scoped()
            .filter_by(
                name=name,
                organization_id=current_user.organization_id,
            )
            .first()
        )

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
        logger.warning(
            "Suppressed exception fallback at app/blueprints/recipes/views/ajax_routes.py:131",
            exc_info=True,
        )
        db.session.rollback()
        logger.error("Error quick-adding ingredient: %s", exc)
        return jsonify({"error": str(exc)}), 500
