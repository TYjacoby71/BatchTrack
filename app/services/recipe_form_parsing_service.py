"""Recipe form parsing data-access boundary.

Synopsis:
Encapsulates DB-backed helpers used by `recipes/form_parsing.py` so form parsing
stays focused on payload transformation.
"""

from __future__ import annotations

import logging

from app.extensions import db
from app.models import GlobalItem, InventoryItem
from app.models.unit import Unit

logger = logging.getLogger(__name__)


class RecipeFormParsingService:
    """Data/session helpers for recipe form parsing workflows."""

    @staticmethod
    def find_unit_for_portion_name(
        *,
        portion_name: str,
        organization_id: int | None,
    ) -> Unit | None:
        try:
            return (
                Unit.query.filter(Unit.name == portion_name)
                .order_by((Unit.organization_id == organization_id).desc())
                .first()
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:29",
                exc_info=True,
            )
            return None

    @staticmethod
    def create_custom_count_unit(
        *,
        portion_name: str,
        organization_id: int | None,
        created_by: int | None,
    ) -> Unit:
        unit = Unit(
            name=portion_name,
            unit_type="count",
            base_unit="count",
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=organization_id,
            created_by=created_by,
        )
        db.session.add(unit)
        db.session.flush()
        return unit

    @staticmethod
    def create_custom_count_unit_for_org(
        *,
        portion_name: str,
        organization_id: int | None,
        user_id: int | None,
    ) -> int | None:
        try:
            unit = RecipeFormParsingService.create_custom_count_unit(
                portion_name=portion_name,
                organization_id=organization_id,
                created_by=user_id,
            )
            return unit.id
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:58",
                exc_info=True,
            )
            db.session.rollback()
            return None

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

    @staticmethod
    def get_global_item(global_item_id: int | None) -> GlobalItem | None:
        if not global_item_id:
            return None
        try:
            return db.session.get(GlobalItem, int(global_item_id))
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:78",
                exc_info=True,
            )
            return None

    @staticmethod
    def get_global_item_by_id(global_item_id: int | None) -> GlobalItem | None:
        return RecipeFormParsingService.get_global_item(global_item_id)

    @staticmethod
    def find_org_inventory_item_for_global(
        *,
        organization_id: int | None,
        global_item_id: int,
        item_type: str,
    ) -> InventoryItem | None:
        if not organization_id:
            return None
        try:
            return (
                InventoryItem.scoped()
                .filter_by(
                    organization_id=organization_id,
                    global_item_id=global_item_id,
                    type=item_type,
                )
                .order_by(InventoryItem.id.asc())
                .first()
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:105",
                exc_info=True,
            )
            return None

    @staticmethod
    def find_inventory_item_by_global_item_for_org(
        *,
        organization_id: int | None,
        global_item_id: int,
        item_type: str,
    ) -> InventoryItem | None:
        return RecipeFormParsingService.find_org_inventory_item_for_global(
            organization_id=organization_id,
            global_item_id=global_item_id,
            item_type=item_type,
        )

    @staticmethod
    def find_org_inventory_item_name_match(
        *,
        organization_id: int | None,
        name: str,
        item_type: str,
    ) -> InventoryItem | None:
        if not organization_id:
            return None
        from sqlalchemy import func

        try:
            return (
                InventoryItem.scoped()
                .filter(
                    InventoryItem.organization_id == organization_id,
                    func.lower(InventoryItem.name) == func.lower(db.literal(name)),
                    InventoryItem.type == item_type,
                )
                .order_by(InventoryItem.id.asc())
                .first()
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:145",
                exc_info=True,
            )
            return None

    @staticmethod
    def find_inventory_item_by_name_for_org_type(
        *,
        organization_id: int | None,
        item_name: str,
        item_type: str,
    ) -> InventoryItem | None:
        return RecipeFormParsingService.find_org_inventory_item_name_match(
            organization_id=organization_id,
            name=item_name,
            item_type=item_type,
        )

    @staticmethod
    def link_inventory_item_to_global(
        *, item: InventoryItem, global_item_id: int
    ) -> None:
        item.global_item_id = global_item_id
        item.ownership = "global"
        db.session.flush()

    @staticmethod
    def assign_global_ownership_and_flush(
        *,
        inventory_item: InventoryItem,
        global_item_id: int,
    ) -> bool:
        try:
            RecipeFormParsingService.link_inventory_item_to_global(
                item=inventory_item,
                global_item_id=global_item_id,
            )
            return True
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/recipe_form_parsing_service.py:180",
                exc_info=True,
            )
            db.session.rollback()
            return False

    @staticmethod
    def find_existing_unit_for_portion_name(
        *,
        portion_name: str,
        organization_id: int | None,
    ) -> Unit | None:
        return RecipeFormParsingService.find_unit_for_portion_name(
            portion_name=portion_name,
            organization_id=organization_id,
        )
