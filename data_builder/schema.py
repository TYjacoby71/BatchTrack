"""Pydantic models that describe the AI payload contract."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .config import DEFAULT_INGREDIENT_CATEGORY_TAGS, DEFAULT_PHYSICAL_FORMS


class TaxonomyTags(BaseModel):
    ingredient_category_tags: List[str] = Field(default_factory=list)
    function_tags: List[str] = Field(default_factory=list)
    application_tags: List[str] = Field(default_factory=list)


class Ingredient(BaseModel):
    common_name: str
    inci_name: Optional[str] = None
    cas_number: Optional[str] = None
    description: Optional[str] = None
    is_active_ingredient: Optional[bool] = None
    safety_notes: Optional[str] = None
    taxonomies: TaxonomyTags = Field(default_factory=TaxonomyTags)


class Item(BaseModel):
    item_name: str
    physical_form: str
    density_g_ml: Optional[float] = None
    shelf_life_days: Optional[int] = None
    ph_value: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @validator("physical_form")
    def validate_physical_form(cls, value: str) -> str:
        if value not in DEFAULT_PHYSICAL_FORMS:
            raise ValueError(
                f"physical_form '{value}' is not in the approved list: {DEFAULT_PHYSICAL_FORMS}"
            )
        return value


class IngredientPayload(BaseModel):
    ingredient: Ingredient
    items: List[Item]

    @validator("items")
    def ensure_items_present(cls, value: List[Item]) -> List[Item]:
        if not value:
            raise ValueError("At least one item must be provided per ingredient")
        return value

    @validator("ingredient")
    def ensure_category_present(cls, value: Ingredient) -> Ingredient:
        tags = value.taxonomies.ingredient_category_tags
        if not tags:
            raise ValueError("ingredient_category_tags must include at least one entry")
        unknown = [tag for tag in tags if tag not in DEFAULT_INGREDIENT_CATEGORY_TAGS]
        if unknown:
            raise ValueError(
                "Unknown ingredient_category_tags detected: " + ", ".join(unknown)
            )
        return value


class ErrorPayload(BaseModel):
    error: str


__all__ = [
    "IngredientPayload",
    "Ingredient",
    "Item",
    "TaxonomyTags",
    "ErrorPayload",
]
