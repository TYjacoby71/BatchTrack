from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from sqlalchemy import func

from app.extensions import db
from app.models import (
    GlobalItem,
    InventoryItem,
    Recipe,
    RecipeIngredient,
    Unit,
)
from app.models.global_item_alias import GlobalItemAlias
from app.services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _IngredientInput:
    item_id: int
    quantity: float
    unit: str


@dataclass
class _RecipeSignature:
    totals: dict[str, float]
    proportions: dict[str, float] | None


class RecipeProportionalityService:
    """Centralized proportionality comparisons for recipes using UUCS + Global Library."""

    WEIGHT_TARGET_UNIT = "gram"
    VOLUME_TARGET_UNIT = "milliliter"
    COUNT_TARGET_UNIT = "count"
    PROPORTION_TOLERANCE = 0.0001  # 0.01%
    ABSOLUTE_TOLERANCE = 1e-6

    _WEIGHT_TYPES = {"weight", "mass"}
    _VOLUME_TYPES = {"volume", "liquid"}

    @classmethod
    def are_recipes_proportionally_identical(
        cls,
        recipe_a: Recipe | Sequence[RecipeIngredient] | Sequence[Mapping],
        recipe_b: Recipe | Sequence[RecipeIngredient] | Sequence[Mapping],
    ) -> bool:
        """Compare two recipes (or ingredient payloads) for proportional identity."""
        sig_a = cls._build_signature(recipe_a)
        sig_b = cls._build_signature(recipe_b)
        return cls._compare_signatures(sig_a, sig_b)

    # -- Signature construction -------------------------------------------------
    @classmethod
    def _build_signature(
        cls,
        source: Recipe | Sequence[RecipeIngredient] | Sequence[Mapping] | None,
    ) -> _RecipeSignature:
        totals: dict[str, float] = {}
        if not source:
            return _RecipeSignature(totals=totals, proportions=None)

        for ing in cls._collect_ingredients(source):
            inventory_item = cls._get_inventory_item(ing.item_id)
            if not inventory_item:
                continue

            converted = cls._convert_to_base(
                amount=ing.quantity,
                unit_name=ing.unit,
                inventory_item=inventory_item,
            )
            if converted is None:
                continue
            amount_value, unit_basis = converted
            canonical_key = cls._build_canonical_key(
                inventory_item=inventory_item,
                unit_basis=unit_basis or ing.unit,
            )
            if not canonical_key:
                continue
            totals[canonical_key] = totals.get(canonical_key, 0.0) + amount_value

        if not totals:
            return _RecipeSignature(totals=totals, proportions=None)

        total_amount = sum(totals.values())
        if total_amount <= 0:
            return _RecipeSignature(totals=totals, proportions=None)

        proportions = {
            key: totals[key] / total_amount for key in totals
        }
        return _RecipeSignature(totals=totals, proportions=proportions)

    @classmethod
    def _collect_ingredients(
        cls,
        source: Recipe | Sequence[RecipeIngredient] | Sequence[Mapping],
    ) -> Iterable[_IngredientInput]:
        if isinstance(source, Recipe):
            iterable = getattr(source, "recipe_ingredients", []) or []
        else:
            iterable = source

        for entry in iterable:
            if isinstance(entry, RecipeIngredient):
                item_id = entry.inventory_item_id
                quantity = entry.quantity
                unit_name = entry.unit
            elif isinstance(entry, Mapping):
                item_id = entry.get("item_id") or entry.get("inventory_item_id")
                quantity = entry.get("quantity")
                unit_name = entry.get("unit")
            else:
                continue

            if not item_id or unit_name in (None, ""):
                continue
            try:
                normalized_quantity = float(quantity)
            except (TypeError, ValueError):
                continue
            if normalized_quantity < 0:
                continue

            yield _IngredientInput(
                item_id=int(item_id),
                quantity=normalized_quantity,
                unit=str(unit_name).strip(),
            )

    # -- Comparison -------------------------------------------------------------
    @classmethod
    def _compare_signatures(cls, sig_a: _RecipeSignature, sig_b: _RecipeSignature) -> bool:
        if not sig_a.totals and not sig_b.totals:
            return True
        if bool(sig_a.proportions) and bool(sig_b.proportions):
            return cls._compare_proportions(sig_a.proportions, sig_b.proportions)
        if bool(sig_a.proportions) != bool(sig_b.proportions):
            return False
        return cls._compare_totals(sig_a.totals, sig_b.totals)

    @classmethod
    def _compare_proportions(
        cls,
        a: dict[str, float],
        b: dict[str, float],
    ) -> bool:
        if set(a.keys()) != set(b.keys()):
            return False
        for key in a.keys():
            if abs(a[key] - b[key]) > cls.PROPORTION_TOLERANCE:
                return False
        return True

    @classmethod
    def _compare_totals(
        cls,
        a: dict[str, float],
        b: dict[str, float],
    ) -> bool:
        if set(a.keys()) != set(b.keys()):
            return False
        for key in a.keys():
            if abs(a[key] - b[key]) > cls.ABSOLUTE_TOLERANCE:
                return False
        return True

    # -- Canonicalization helpers ----------------------------------------------
    @classmethod
    def _get_inventory_item(cls, item_id: int) -> InventoryItem | None:
        return db.session.get(InventoryItem, item_id)

    @classmethod
    def _build_canonical_key(
        cls,
        *,
        inventory_item: InventoryItem,
        unit_basis: str,
    ) -> str | None:
        canonical = None
        try:
            if inventory_item.global_item_id:
                canonical = f"global:{inventory_item.global_item_id}"
            else:
                global_item = cls._lookup_global_item_by_name(inventory_item.name)
                if global_item:
                    canonical = f"global:{global_item.id}"
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Failed resolving canonical ingredient: %s", exc)

        if not canonical:
            canonical = f"inventory:{inventory_item.id}"
        normalized_unit = (unit_basis or "").strip().lower() or "unit"
        return f"{canonical}|{normalized_unit}"

    @classmethod
    def _lookup_global_item_by_name(cls, name: str | None) -> GlobalItem | None:
        normalized = cls._normalize_name(name)
        if not normalized:
            return None
        match = (
            db.session.query(GlobalItem)
            .filter(func.lower(GlobalItem.name) == normalized)
            .first()
        )
        if not match:
            alias = (
                db.session.query(GlobalItemAlias)
                .filter(func.lower(GlobalItemAlias.alias) == normalized)
                .first()
            )
            if alias:
                match = db.session.get(GlobalItem, alias.global_item_id)

        return match

    @staticmethod
    def _normalize_name(name: str | None) -> str:
        if not name:
            return ""
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", name.lower()).strip()
        if not cleaned:
            return ""
        tokens = [token for token in cleaned.split() if token]
        return " ".join(tokens)

    # -- Conversion helpers -----------------------------------------------------
    @classmethod
    def _convert_to_base(
        cls,
        *,
        amount: float,
        unit_name: str,
        inventory_item: InventoryItem,
    ) -> tuple[float, str] | None:
        target_unit, unit_type = cls._determine_target_unit(unit_name)
        if target_unit == unit_name:
            return amount, target_unit

        result = ConversionEngine.convert_units(
            amount=amount,
            from_unit=unit_name,
            to_unit=target_unit,
            ingredient_id=inventory_item.id,
            density=inventory_item.density or getattr(getattr(inventory_item, "global_item", None), "density", None),
            organization_id=inventory_item.organization_id,
        )
        if not result.get("success"):
            logger.debug(
                "Conversion failure for ingredient %s (%s -> %s): %s",
                inventory_item.id,
                unit_name,
                target_unit,
                result.get("error_code"),
            )
            return None
        converted_value = result.get("converted_value")
        if converted_value is None:
            return None
        return float(converted_value), target_unit

    @classmethod
    def _determine_target_unit(cls, unit_name: str) -> tuple[str, str | None]:
        unit = cls._get_unit(unit_name)
        if not unit:
            return unit_name, None
        unit_type = (unit.unit_type or "").lower()
        if unit_type in cls._WEIGHT_TYPES:
            return cls.WEIGHT_TARGET_UNIT, unit_type
        if unit_type in cls._VOLUME_TYPES:
            return cls.VOLUME_TARGET_UNIT, unit_type
        if unit_type == "count":
            return cls.COUNT_TARGET_UNIT, unit_type
        base = (unit.base_unit or "").strip()
        return (base or unit.name), unit_type

    @classmethod
    def _get_unit(cls, unit_name: str) -> Unit | None:
        normalized = (unit_name or "").strip().lower()
        if not normalized:
            return None
        return Unit.query.filter(func.lower(Unit.name) == normalized).first()
