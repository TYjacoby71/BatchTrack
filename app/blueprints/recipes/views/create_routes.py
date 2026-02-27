"""Recipe create/edit routes.

Synopsis:
Handles new recipe creation, variation/test creation, edits, and forced-edit overrides.

Glossary:
- Variation: Branch off a master recipe with its own version line.
- Test: Editable draft tied to a master/variation before promotion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from wtforms.validators import ValidationError

from app.extensions import db
from app.models import InventoryItem, Recipe
from app.models.product_category import ProductCategory
from app.services.lineage_service import format_label_prefix, generate_variation_prefix
from app.services.recipe_proportionality_service import RecipeProportionalityService
from app.services.recipe_service import (
    build_test_template,
    create_recipe,
)
from app.services.recipe_service import (
    create_test_version as create_test_version_service,
)
from app.services.recipe_service import (
    duplicate_recipe,
    get_next_test_sequence,
    get_recipe_details,
    update_recipe,
)
from app.services.recipe_service._core import _derive_variation_name
from app.utils.permissions import (
    get_effective_organization_id,
    has_permission,
    require_permission,
)
from app.utils.recipe_batch_counts import count_batches_for_recipe
from app.utils.seo import slugify_value
from app.utils.timezone_utils import TimezoneUtils

from .. import recipes_bp
from ..form_utils import (
    build_draft_prompt,
    build_prefill_from_form,
    build_recipe_submission,
    create_variation_template,
    get_recipe_form_data,
    get_submission_status,
    parse_service_error,
    recipe_from_form,
    render_recipe_form,
    safe_int,
    serialize_assoc_rows,
    serialize_prefill_rows,
)

logger = logging.getLogger(__name__)


# --- Resolve active org ---
# Purpose: Determine the active organization for recipe operations.
def _resolve_active_org_id():
    org_id = get_effective_organization_id()
    if org_id:
        return org_id
    try:
        return getattr(current_user, "organization_id", None)
    except Exception:
        return None


# --- Ensure variation changes ---
# Purpose: Reject variations without ingredient-level changes.
def _ensure_variation_has_changes(parent_recipe, variation_ingredients):
    if RecipeProportionalityService.are_recipes_proportionally_identical(
        variation_ingredients,
        parent_recipe.recipe_ingredients,
    ):
        raise ValidationError(
            "A variation must have at least one change to an ingredient or proportion. No changes were detected."
        )


# --- Hydrate variation draft ---
# Purpose: Ensure variation drafts have lineage metadata for display.
def _hydrate_variation_draft(draft, parent_recipe):
    draft.is_master = False
    draft.recipe_group_id = parent_recipe.recipe_group_id
    draft.recipe_group = parent_recipe.recipe_group
    draft.parent_master = parent_recipe
    draft.version_number = 1
    if not getattr(draft, "variation_name", None):
        draft.variation_name = _derive_variation_name(draft.name, parent_recipe.name)
    if not getattr(draft, "variation_prefix", None):
        draft.variation_prefix = generate_variation_prefix(
            draft.variation_name or draft.name,
            parent_recipe.recipe_group_id,
        )


# --- Ensure test changes ---
# Purpose: Require tests to change ingredients, yield, or instructions.
def _ensure_test_has_changes(base_recipe, payload):
    submitted_ingredients = payload.get("ingredients") or []
    ingredients_same = (
        RecipeProportionalityService.are_recipes_proportionally_identical(
            submitted_ingredients,
            base_recipe.recipe_ingredients,
        )
    )
    submitted_instructions = (payload.get("instructions") or "").strip()
    base_instructions = (base_recipe.instructions or "").strip()
    instructions_same = submitted_instructions == base_instructions
    submitted_yield = payload.get("yield_amount")
    submitted_unit = (payload.get("yield_unit") or "").strip()
    base_yield = float(base_recipe.predicted_yield or 0)
    base_unit = (base_recipe.predicted_yield_unit or "").strip()
    yield_same = (float(submitted_yield or 0) == base_yield) and (
        submitted_unit == base_unit
    )

    if ingredients_same and instructions_same and yield_same:
        raise ValidationError(
            "Tests must change ingredients, yield, or instructions to create a new version."
        )


# --- Enforce anti-plagiarism ---
# Purpose: Block recipes that duplicate purchased formulas.
def _enforce_anti_plagiarism(ingredients, *, skip_check: bool):
    if skip_check or not ingredients:
        return
    if not has_permission(current_user, "recipes.create_variations"):
        return

    org_id = _resolve_active_org_id()
    if not org_id:
        return

    purchased_recipes = (
        Recipe.scoped().options(joinedload(Recipe.recipe_ingredients))
        .filter(
            Recipe.organization_id == org_id,
            Recipe.org_origin_purchased.is_(True),
            Recipe.test_sequence.is_(None),
        )
        .all()
    )

    for purchased in purchased_recipes:
        if RecipeProportionalityService.are_recipes_proportionally_identical(
            ingredients,
            purchased.recipe_ingredients,
        ):
            raise ValidationError(
                "This recipe is identical to a recipe you have purchased. Please create a variation of your purchased recipe instead."
            )


# =========================================================
# RECIPE CREATION
# =========================================================
# --- New recipe ---
# Purpose: Create a new master recipe.
@recipes_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("recipes.create")
def new_recipe():
    if request.method == "POST":
        is_clone = request.form.get("is_clone") == "true"
        cloned_from_id = safe_int(request.form.get("cloned_from_id"))
        target_status = get_submission_status(request.form)
        try:
            submission = build_recipe_submission(request.form, request.files)
            if not submission.ok:
                flash(submission.error, "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                form_recipe = recipe_from_form(request.form)
                return render_recipe_form(
                    recipe=form_recipe,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    is_clone=is_clone,
                    cloned_from_id=cloned_from_id,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            payload.update(
                {
                    "status": target_status,
                    "cloned_from_id": cloned_from_id,
                }
            )

            submitted_ingredients = payload.get("ingredients") or []

            try:
                _enforce_anti_plagiarism(
                    submitted_ingredients,
                    skip_check=bool(cloned_from_id),
                )
            except ValidationError as exc:
                flash(str(exc), "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                form_recipe = recipe_from_form(request.form)
                return render_recipe_form(
                    recipe=form_recipe,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    is_clone=is_clone,
                    cloned_from_id=cloned_from_id,
                    form_values=request.form,
                )

            success, result = create_recipe(**payload)

            if success:
                try:
                    created_names = []
                    for ing in submitted_ingredients:
                        item = db.session.get(InventoryItem, ing["item_id"])
                        if (
                            item
                            and not getattr(item, "global_item_id", None)
                            and float(getattr(item, "quantity", 0) or 0) == 0.0
                        ):
                            created_names.append(item.name)
                    if created_names:
                        flash(
                            "Added {} new inventory item(s) from this recipe: {}".format(
                                len(created_names), ", ".join(created_names)
                            )
                        )
                except Exception:
                    pass
                if target_status == "draft":
                    flash(
                        "Recipe saved as a draft. You can finish it later from the recipes list.",
                        "info",
                    )
                else:
                    flash("Recipe published successfully.", "success")
                try:
                    from flask import session as _session

                    _session.pop("tool_draft", None)
                    _session.pop("tool_draft_meta", None)
                except Exception:
                    pass
                return redirect(url_for("recipes.view_recipe", recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(
                missing_fields, target_status, error_message
            )
            flash(f"Error creating recipe: {error_message}", "error")
            ingredient_prefill, consumable_prefill = build_prefill_from_form(
                request.form
            )
            form_recipe = recipe_from_form(request.form)
            return render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        except Exception as exc:
            db.session.rollback()
            logger.exception("Error creating recipe: %s", exc)
            flash("An unexpected error occurred", "error")
            ingredient_prefill, consumable_prefill = build_prefill_from_form(
                request.form
            )
            form_recipe = recipe_from_form(request.form)
            return render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form,
            )

    from flask import session

    draft = session.get("tool_draft", None)
    try:
        meta = session.get("tool_draft_meta") or {}
        created_at = meta.get("created_at")
        if created_at:
            created_dt = datetime.fromisoformat(created_at)
            created_dt = TimezoneUtils.ensure_timezone_aware(created_dt)
            if datetime.now(timezone.utc) - created_dt > timedelta(hours=72):
                session.pop("tool_draft", None)
                session.pop("tool_draft_meta", None)
                draft = None
    except Exception:
        pass
    prefill = None
    if isinstance(draft, dict):
        try:
            prefill = Recipe(
                name=draft.get("name") or "",
                instructions=draft.get("instructions") or "",
                predicted_yield=float(draft.get("predicted_yield") or 0) or 0.0,
                predicted_yield_unit=(draft.get("predicted_yield_unit") or ""),
            )
            cat_name = (draft.get("category_name") or "").strip()
            if cat_name:
                cat = ProductCategory.query.filter(
                    func.lower(ProductCategory.name) == func.lower(db.literal(cat_name))
                ).first()
                if cat:
                    prefill.category_id = cat.id
        except Exception:
            prefill = None

    return render_recipe_form(recipe=prefill)


# =========================================================
# VARIATIONS & TESTS
# =========================================================
# --- Create variation ---
# Purpose: Create a variation from a published master.
@recipes_bp.route("/<int:recipe_id>/variation", methods=["GET", "POST"])
@login_required
@require_permission("recipes.create_variations")
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash("Parent recipe not found.", "error")
            return redirect(url_for("recipes.list_recipes"))
        if parent.is_archived:
            flash("Archived recipes cannot accept new variations.", "error")
            return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
        if not parent.is_master or parent.test_sequence is not None:
            flash(
                "Variations can only be created from a published master recipe.",
                "error",
            )
            return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))

        if request.method == "POST":
            target_status = get_submission_status(request.form)
            submission = build_recipe_submission(
                request.form, request.files, defaults=parent
            )
            if not submission.ok:
                flash(submission.error, "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                variation_draft = recipe_from_form(request.form, base_recipe=parent)
                variation_draft.parent_recipe_id = parent.id
                _hydrate_variation_draft(variation_draft, parent)
                return render_recipe_form(
                    recipe=variation_draft,
                    is_variation=True,
                    parent_recipe=parent,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            payload.update(
                {
                    "parent_recipe_id": parent.id,
                    "status": target_status,
                }
            )

            if not payload.get("label_prefix") and parent.label_prefix:
                payload["label_prefix"] = ""

            try:
                _ensure_variation_has_changes(parent, payload.get("ingredients") or [])
            except ValidationError as exc:
                flash(str(exc), "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                variation_draft = recipe_from_form(request.form, base_recipe=parent)
                variation_draft.parent_recipe_id = parent.id
                _hydrate_variation_draft(variation_draft, parent)
                return render_recipe_form(
                    recipe=variation_draft,
                    is_variation=True,
                    parent_recipe=parent,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            if parent.org_origin_purchased:
                payload["is_sellable"] = True
            elif getattr(parent, "is_sellable", True) is False:
                payload["is_sellable"] = False

            success, result = create_recipe(**payload)

            if success:
                if target_status == "draft":
                    flash("Variation saved as a draft.", "info")
                else:
                    flash("Recipe variation created successfully.")
                return redirect(url_for("recipes.view_recipe", recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(
                missing_fields, target_status, error_message
            )
            flash(f"Error creating variation: {error_message}", "error")
            ingredient_prefill, consumable_prefill = build_prefill_from_form(
                request.form
            )
            variation_draft = recipe_from_form(request.form, base_recipe=parent)
            variation_draft.parent_recipe_id = parent.id
            _hydrate_variation_draft(variation_draft, parent)
            return render_recipe_form(
                recipe=variation_draft,
                is_variation=True,
                parent_recipe=parent,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        new_variation = create_variation_template(parent)
        requested_name = (request.args.get("variation_name") or "").strip()
        if requested_name:
            new_variation.name = requested_name
            new_variation.variation_name = requested_name
            new_variation.variation_prefix = generate_variation_prefix(
                requested_name,
                parent.recipe_group_id,
            )
        ingredient_prefill = serialize_assoc_rows(parent.recipe_ingredients)
        consumable_prefill = serialize_assoc_rows(parent.recipe_consumables)

        return render_recipe_form(
            recipe=new_variation,
            is_variation=True,
            parent_recipe=parent,
            ingredient_prefill=ingredient_prefill,
            consumable_prefill=consumable_prefill,
        )

    except Exception as exc:
        flash(f"Error creating variation: {exc}", "error")
        logger.exception("Error creating variation: %s", exc)
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))


# --- Create test version ---
# Purpose: Create a test version for any published non-test recipe.
@recipes_bp.route("/<int:recipe_id>/test", methods=["GET", "POST"])
@login_required
@require_permission("recipes.create_variations")
def create_test_version(recipe_id):
    try:
        base = get_recipe_details(recipe_id)
        if not base:
            flash("Recipe not found.", "error")
            return redirect(url_for("recipes.list_recipes"))
        if base.is_archived:
            flash("Archived recipes cannot be tested.", "error")
            return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
        if base.status != "published":
            flash("Publish the recipe before creating tests.", "error")
            return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
        if base.test_sequence is not None:
            flash(
                "Tests cannot be created from test recipes.",
                "error",
            )
            return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))

        if request.method == "POST":
            target_status = get_submission_status(request.form)
            submission = build_recipe_submission(
                request.form, request.files, defaults=base
            )
            if not submission.ok:
                flash(submission.error, "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                test_draft = recipe_from_form(request.form, base_recipe=base)
                next_sequence = get_next_test_sequence(base)
                return render_recipe_form(
                    recipe=test_draft,
                    is_test=True,
                    test_base_id=base.id,
                    test_sequence_hint=next_sequence,
                    label_prefix_display=format_label_prefix(
                        base, test_sequence=next_sequence
                    ),
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            try:
                _ensure_test_has_changes(base, payload)
            except ValidationError as exc:
                flash(str(exc), "error")
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                test_draft = recipe_from_form(request.form, base_recipe=base)
                next_sequence = get_next_test_sequence(base)
                return render_recipe_form(
                    recipe=test_draft,
                    is_test=True,
                    test_base_id=base.id,
                    test_sequence_hint=next_sequence,
                    label_prefix_display=format_label_prefix(
                        base, test_sequence=next_sequence
                    ),
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            success, result = create_test_version_service(
                base=base,
                payload=payload,
                target_status=target_status,
            )
            if success:
                if target_status == "draft":
                    flash("Test saved as a draft.", "info")
                else:
                    flash("Test version created successfully.", "success")
                return redirect(url_for("recipes.view_recipe", recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(
                missing_fields, target_status, error_message
            )
            flash(f"Error creating test: {error_message}", "error")
            ingredient_prefill, consumable_prefill = build_prefill_from_form(
                request.form
            )
            test_draft = recipe_from_form(request.form, base_recipe=base)
            next_sequence = get_next_test_sequence(base)
            return render_recipe_form(
                recipe=test_draft,
                is_test=True,
                test_base_id=base.id,
                test_sequence_hint=next_sequence,
                label_prefix_display=format_label_prefix(
                    base, test_sequence=next_sequence
                ),
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        next_sequence = get_next_test_sequence(base)
        test_template = build_test_template(base, test_sequence=next_sequence)

        ingredient_prefill = serialize_assoc_rows(base.recipe_ingredients)
        consumable_prefill = serialize_assoc_rows(base.recipe_consumables)

        return render_recipe_form(
            recipe=test_template,
            is_test=True,
            test_base_id=base.id,
            test_sequence_hint=next_sequence,
            label_prefix_display=format_label_prefix(base, test_sequence=next_sequence),
            ingredient_prefill=ingredient_prefill,
            consumable_prefill=consumable_prefill,
        )

    except Exception as exc:
        flash(f"Error creating test: {exc}", "error")
        logger.exception("Error creating test: %s", exc)
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))


# =========================================================
# EDITING
# =========================================================
# --- Edit recipe ---
# Purpose: Edit a recipe, allowing forced overrides for published masters.
@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("recipes.edit")
def edit_recipe(recipe_id):
    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash("Recipe not found.", "error")
        return redirect(url_for("recipes.list_recipes"))

    existing_batches = count_batches_for_recipe(
        recipe,
        organization_id=getattr(current_user, "organization_id", None),
    )
    force_edit = str(
        request.args.get("force") or request.form.get("force_edit") or ""
    ).lower() in {"1", "true", "yes"}
    if recipe.is_locked:
        flash("This recipe is locked and cannot be edited.", "error")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
    if recipe.is_archived:
        flash("Archived recipes cannot be edited.", "error")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
    if recipe.status == "published" and recipe.test_sequence is None and not force_edit:
        flash("Published versions are locked. Create a test to make edits.", "error")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
    if recipe.test_sequence is not None and existing_batches > 0:
        flash("Tests cannot be edited after running batches.", "error")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))

    draft_prompt = None
    form_override = None
    if request.method == "POST":
        target_status = get_submission_status(request.form)
        try:
            submission = build_recipe_submission(
                request.form, request.files, defaults=recipe, existing=recipe
            )
            if not submission.ok:
                flash(submission.error, "error")
                form_override = request.form
                ingredient_prefill, consumable_prefill = build_prefill_from_form(
                    request.form
                )
                return render_recipe_form(
                    recipe=recipe,
                    edit_mode=True,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=form_override,
                    force_edit=force_edit,
                )

            payload = dict(submission.kwargs)
            payload["status"] = target_status
            payload["is_test"] = (
                str(request.form.get("is_test") or "").lower() == "true"
            )

            success, result = update_recipe(
                recipe_id=recipe_id,
                allow_published_edit=force_edit,
                **payload,
            )

            if success:
                if target_status == "draft":
                    flash("Recipe saved as a draft.", "info")
                else:
                    flash("Recipe updated successfully.")
                return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))
            else:
                error_message, missing_fields = parse_service_error(result)
                draft_prompt = build_draft_prompt(
                    missing_fields, target_status, error_message
                )
                form_override = request.form
                flash(f"Error updating recipe: {error_message}", "error")

        except Exception as exc:
            logger.exception("Error updating recipe: %s", exc)
            flash("An unexpected error occurred", "error")

    form_data = get_recipe_form_data()

    return render_template(
        "pages/recipes/recipe_form.html",
        recipe=recipe,
        edit_mode=True,
        is_test=bool(recipe.test_sequence),
        existing_batches=existing_batches,
        draft_prompt=draft_prompt,
        form_values=form_override,
        force_edit=force_edit,
        **form_data,
    )


# =========================================================
# LEGACY & IMPORT
# =========================================================
# --- Clone recipe (deprecated) ---
# Purpose: Redirect clone requests to new version flow.
@recipes_bp.route("/<int:recipe_id>/clone")
@login_required
@require_permission("recipes.create")
def clone_recipe(recipe_id):
    try:
        flash(
            "Cloning recipes has been retired. Use Create New Version instead.",
            "warning",
        )

    except Exception as exc:
        db.session.rollback()
        flash(f"Error handling clone request: {exc}", "error")
        logger.exception("Error cloning recipe: %s", exc)

    return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))


# --- Import recipe ---
# Purpose: Import a public recipe into the org library.
@recipes_bp.route("/<int:recipe_id>/import", methods=["GET"])
@login_required
@require_permission("recipes.view")
def import_recipe(recipe_id: int):
    effective_org_id = get_effective_organization_id()
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        flash("Recipe not found.", "error")
        return redirect(url_for("recipe_library_bp.recipe_library"))

    detail_url = url_for(
        "recipe_library_bp.recipe_library_detail",
        recipe_id=recipe.id,
        slug=slugify_value(recipe.name),
    )

    if not effective_org_id:
        flash("Select an organization before importing a recipe.", "error")
        return redirect(detail_url)

    if (
        not recipe.is_public
        or recipe.status != "published"
        or recipe.test_sequence is not None
        or recipe.marketplace_status != "listed"
        or recipe.marketplace_blocked
    ):
        flash("This recipe is not available for import right now.", "error")
        return redirect(detail_url)

    try:
        success, payload = duplicate_recipe(
            recipe_id,
            allow_cross_org=True,
            target_org_id=effective_org_id,
        )
    except PermissionError as exc:
        logger.warning("Import blocked for recipe %s: %s", recipe_id, exc)
        flash("You do not have permission to import this recipe.", "error")
        return redirect(detail_url)

    if not success:
        flash(f"Error importing recipe: {payload}", "error")
        return redirect(detail_url)

    template_recipe = payload["template"]
    ingredient_prefill = serialize_prefill_rows(payload["ingredients"])
    consumable_prefill = serialize_prefill_rows(payload["consumables"])

    if recipe.is_for_sale:
        flash("Confirm your purchase before importing paid recipes.", "warning")
    else:
        flash(
            "Review the imported recipe and click Save to add it to your workspace.",
            "info",
        )

    return render_recipe_form(
        recipe=template_recipe,
        is_clone=True,
        ingredient_prefill=ingredient_prefill,
        consumable_prefill=consumable_prefill,
        cloned_from_id=payload.get("cloned_from_id"),
        form_values=None,
        is_import=True,
    )
