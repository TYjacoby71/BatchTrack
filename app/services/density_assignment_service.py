from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

from ..extensions import db
from ..models import GlobalItem, IngredientCategory, InventoryItem


class DensityAssignmentService:
    """Service for automatically assigning densities based on reference guide"""

    @staticmethod
    def _load_reference_data_from_db() -> Dict:
        """Load density reference data from database (GlobalItem)"""
        try:
            items = GlobalItem.query.filter_by(item_type="ingredient").all()
            payload_items = []
            for gi in items:
                payload_items.append(
                    {
                        "name": gi.name,
                        "density_g_per_ml": gi.density,
                        "aliases": gi.aliases or [],
                        "category": (
                            gi.ingredient_category.name
                            if gi.ingredient_category
                            else "Other"
                        ),
                    }
                )
            return {"common_densities": payload_items}
        except Exception as e:
            current_app.logger.error(
                f"Failed to load density reference from DB: {str(e)}"
            )
            return {"common_densities": []}

    @staticmethod
    def build_global_library_density_options(
        include_uncategorized: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return global library ingredient density options grouped by category."""
        payload: List[Dict[str, Any]] = []

        categories = (
            IngredientCategory.query.filter(
                IngredientCategory.is_global_category.is_(True),
                IngredientCategory.organization_id.is_(None),
            )
            .order_by(IngredientCategory.name.asc())
            .all()
        )

        for category in categories:
            items = (
                GlobalItem.query.filter(
                    GlobalItem.item_type == "ingredient",
                    GlobalItem.ingredient_category_id == category.id,
                )
                .order_by(GlobalItem.name.asc())
                .all()
            )

            payload.append(
                {
                    "name": category.name,
                    "default_density": category.default_density,
                    "description": category.description,
                    "items": [
                        {
                            "id": gi.id,
                            "name": gi.name,
                            "density_g_per_ml": gi.density,
                            "aliases": gi.aliases or [],
                            "ingredient_category_id": gi.ingredient_category_id,
                            "metadata": gi.metadata_json or {},
                        }
                        for gi in items
                        if not getattr(gi, "is_archived", False)
                    ],
                }
            )

        if include_uncategorized:
            uncategorized_items = (
                GlobalItem.query.filter(
                    GlobalItem.item_type == "ingredient",
                    GlobalItem.ingredient_category_id.is_(None),
                )
                .order_by(GlobalItem.name.asc())
                .all()
            )
            filtered = [
                gi
                for gi in uncategorized_items
                if not getattr(gi, "is_archived", False)
            ]
            if filtered:
                payload.append(
                    {
                        "name": "Uncategorized Ingredients",
                        "default_density": None,
                        "description": "Global ingredients without an assigned category.",
                        "items": [
                            {
                                "id": gi.id,
                                "name": gi.name,
                                "density_g_per_ml": gi.density,
                                "aliases": gi.aliases or [],
                                "ingredient_category_id": gi.ingredient_category_id,
                                "metadata": gi.metadata_json or {},
                            }
                            for gi in filtered
                        ],
                    }
                )

        return payload

    @staticmethod
    def _similarity_score(name1: str, name2: str) -> float:
        """Calculate similarity between two ingredient names"""
        return SequenceMatcher(
            None, name1.lower().strip(), name2.lower().strip()
        ).ratio()

    @staticmethod
    def find_best_match(
        ingredient_name: str, threshold: float = 0.7
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Find the best matching reference item or category for an ingredient name
        Returns: (reference_item, match_type) where match_type is 'exact', 'alias', 'similarity', or None
        """
        if not ingredient_name:
            return None, None

        reference_data = DensityAssignmentService._load_reference_data_from_db()
        items = reference_data.get("common_densities", [])

        ingredient_lower = ingredient_name.lower().strip()

        # High-trust keyword heuristic mapping
        # 1) Exact density overrides for certain well-known names
        keyword_to_exact_density = {
            "beeswax": 0.96,
        }
        for keyword, exact_density in keyword_to_exact_density.items():
            if keyword in ingredient_lower:
                return {
                    "name": keyword,
                    "density_g_per_ml": exact_density,
                    "aliases": [],
                    "category": "Waxes",
                }, "exact_keyword_density"

        # 2) Category-level defaults
        keyword_to_category = {
            "wax": "Waxes",
            "oil": "Oils",
            "syrup": "Syrups",
            "flour": "Flours",
            "sugar": "Sugars",
            "salt": "Salts",
            "starch": "Starches",
            "butter": "Fats",
            "alcohol": "Alcohols",
        }
        for keyword, category in keyword_to_category.items():
            if keyword in ingredient_lower:
                # synthesize a category pseudo-item to signal category default usage
                return {
                    "name": None,
                    "density_g_per_ml": None,
                    "aliases": [],
                    "category": category,
                }, "category_keyword"

        # First: Try exact name match
        for item in items:
            if item["name"].lower() == ingredient_lower:
                return item, "exact"

        # Second: Try alias match
        for item in items:
            for alias in item.get("aliases", []):
                if alias.lower() == ingredient_lower:
                    return item, "alias"

        # Third: Try similarity matching
        best_match = None
        best_score = 0

        for item in items:
            # Check main name similarity
            score = DensityAssignmentService._similarity_score(
                ingredient_name, item["name"]
            )
            if score > best_score and score >= threshold:
                best_score = score
                best_match = item

            # Check alias similarities
            for alias in item.get("aliases", []):
                score = DensityAssignmentService._similarity_score(
                    ingredient_name, alias
                )
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = item

        if best_match:
            return best_match, "similarity"

        return None, None

    @staticmethod
    def get_category_options(organization_id: int) -> List[Dict]:
        """Get base ingredient categories with their default densities.
        Source of truth: IngredientCategory.default_density.
        """
        from ..models import IngredientCategory

        try:
            categories = IngredientCategory.query
            if organization_id:
                categories = categories.filter_by(organization_id=organization_id)
            cats = categories.order_by(IngredientCategory.name.asc()).all()
            return [
                {
                    "name": c.name,
                    "items": [],  # optional; not needed for fallback
                    "default_density": c.default_density,
                }
                for c in cats
            ]
        except Exception:
            return []

    @staticmethod
    def assign_density_to_ingredient(
        ingredient: InventoryItem,
        reference_item_name: str = None,
        use_category_default: bool = False,
        category_name: str = None,
    ) -> bool:
        """
        Assign density to an ingredient based on reference guide
        Returns True if density was assigned, False otherwise
        """
        try:
            if reference_item_name:
                # Find specific reference item
                reference_data = DensityAssignmentService._load_reference_data_from_db()
                items = reference_data.get("common_densities", [])

                for item in items:
                    if item["name"] == reference_item_name:
                        ingredient.density = item["density_g_per_ml"]
                        ingredient.reference_item_name = reference_item_name
                        ingredient.density_source = "reference_item"
                        db.session.commit()
                        return True

            elif use_category_default and category_name:
                # Use category default density
                categories = DensityAssignmentService.get_category_options(
                    ingredient.organization_id
                )
                for category in categories:
                    if category["name"] == category_name:
                        ingredient.density = category["default_density"]
                        ingredient.reference_item_name = None
                        ingredient.density_source = "category_default"
                        db.session.commit()
                        return True

            return False

        except Exception as e:
            current_app.logger.error(f"Failed to assign density: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def auto_assign_density_on_creation(ingredient: InventoryItem) -> bool:
        """
        Automatically assign density when creating a new ingredient
        """
        if ingredient.density is not None and ingredient.density > 0:
            return True  # Already has valid density

        # Reset invalid density to None
        if ingredient.density is not None and ingredient.density <= 0:
            ingredient.density = None

        match_item, match_type = DensityAssignmentService.find_best_match(
            ingredient.name
        )

        if match_item and match_type in ["exact", "alias", "exact_keyword_density"]:
            # High confidence match - auto assign
            density_value = match_item["density_g_per_ml"]
            if density_value > 0:  # Ensure we don't assign 0 density
                ingredient.density = density_value
                ingredient.reference_item_name = match_item["name"]
                ingredient.density_source = "auto_assigned"
                current_app.logger.info(
                    f"Auto-assigned density for '{ingredient.name}': {density_value} g/ml from '{match_item['name']}'"
                )
                return True
        elif match_item and match_type == "category_keyword":
            # Assign category default density based on aggregated category defaults
            categories = DensityAssignmentService.get_category_options(
                ingredient.organization_id
            )
            category_name = match_item.get("category")
            for cat in categories:
                if cat["name"].lower() == category_name.lower():
                    ingredient.density = cat["default_density"]
                    ingredient.reference_item_name = None
                    ingredient.density_source = "category_default"
                    current_app.logger.info(
                        f"Auto-assigned category default density for '{ingredient.name}': {cat['default_density']} g/ml from category '{category_name}'"
                    )
                    return True
        elif match_item and match_type == "similarity":
            # Lower confidence - suggest but don't auto-assign
            current_app.logger.info(
                f"Similarity match found for '{ingredient.name}': '{match_item['name']}' (density: {match_item['density_g_per_ml']})"
            )
            return False

        return False
