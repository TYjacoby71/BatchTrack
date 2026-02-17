"""Recipe lineage routes.

Synopsis:
Renders lineage tree views for recipe versions and branches.

Glossary:
- Lineage tree: Graph of recipe versions and variations.
- Current version: Flagged active recipe in a branch.
"""
from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from app.models import Recipe, RecipeLineage
from app.services.recipe_service import get_recipe_details
from app.utils.permissions import _org_tier_includes_permission, has_permission, require_permission
from app.utils.settings import is_feature_enabled

from .. import recipes_bp
from ..lineage_utils import build_lineage_path, build_version_branches, serialize_lineage_tree


# =========================================================
# LINEAGE VIEW
# =========================================================
# --- Recipe lineage ---
# Purpose: Render the lineage tree for a recipe.
# Inputs: Recipe identifier from route path.
# Outputs: Rendered lineage page response or redirect on error.
@recipes_bp.route('/<int:recipe_id>/lineage')
@login_required
@require_permission('recipes.view')
def recipe_lineage(recipe_id):
    try:
        recipe = get_recipe_details(recipe_id)
    except PermissionError:
        flash("You do not have access to this recipe.", "error")
        return redirect(url_for('recipes.list_recipes'))
    except Exception as exc:
        flash(f"Unable to load recipe lineage: {exc}", "error")
        return redirect(url_for('recipes.list_recipes'))

    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    root_id = recipe.root_recipe_id or recipe.id
    relatives = (
        Recipe.query.options(joinedload(Recipe.organization))
        .filter(or_(Recipe.id == root_id, Recipe.root_recipe_id == root_id))
        .order_by(Recipe.created_at.asc())
        .all()
    )

    nodes = {rel.id: {'recipe': rel, 'children': []} for rel in relatives}
    master_parent_overrides: dict[int, int] = {}
    variation_parent_overrides: dict[int, int] = {}

    # Display lineage as version chains so variation versions step down correctly.
    master_versions = sorted(
        [
            rel for rel in relatives
            if rel.is_master and rel.test_sequence is None
        ],
        key=lambda row: (int(getattr(row, "version_number", 0) or 0), int(row.id)),
    )
    for previous, current in zip(master_versions, master_versions[1:]):
        master_parent_overrides[current.id] = previous.id

    variation_versions_by_name: dict[str, list[Recipe]] = {}
    for rel in relatives:
        if rel.is_master or rel.test_sequence is not None:
            continue
        variation_key = (rel.variation_name or rel.name or "").strip().lower()
        if not variation_key:
            continue
        variation_versions_by_name.setdefault(variation_key, []).append(rel)
    for versions in variation_versions_by_name.values():
        versions.sort(key=lambda row: (int(getattr(row, "version_number", 0) or 0), int(row.id)))
        for previous, current in zip(versions, versions[1:]):
            variation_parent_overrides[current.id] = previous.id

    for rel in relatives:
        parent_id = None
        edge_type = None
        if rel.test_sequence is None and rel.is_master and rel.id in master_parent_overrides:
            parent_id = master_parent_overrides[rel.id]
            edge_type = 'master'
        elif rel.test_sequence is None and not rel.is_master and rel.id in variation_parent_overrides:
            parent_id = variation_parent_overrides[rel.id]
            edge_type = 'variation'
        elif rel.parent_recipe_id and rel.parent_recipe_id in nodes:
            parent_id = rel.parent_recipe_id
            edge_type = 'test' if rel.test_sequence else 'variation'
        elif rel.cloned_from_id and rel.cloned_from_id in nodes:
            parent_id = rel.cloned_from_id
            edge_type = 'clone'
        elif rel.id != root_id and rel.root_recipe_id and rel.root_recipe_id in nodes:
            parent_id = rel.root_recipe_id
            edge_type = 'root'

        if parent_id and edge_type:
            nodes[parent_id]['children'].append({'id': rel.id, 'edge': edge_type})

    root_recipe = nodes.get(root_id, {'recipe': recipe})
    lineage_tree = serialize_lineage_tree(root_recipe['recipe'], nodes)
    lineage_path = build_lineage_path(recipe.id, nodes, root_id)
    master_branches = []
    variation_branches = []
    if recipe.recipe_group_id:
        group_versions = (
            Recipe.query.filter(Recipe.recipe_group_id == recipe.recipe_group_id)
            .order_by(
                Recipe.is_master.desc(),
                Recipe.variation_name.asc().nullsfirst(),
                Recipe.version_number.desc(),
                Recipe.test_sequence.asc().nullsfirst(),
            )
            .all()
        )
        master_branches, variation_branches = build_version_branches(group_versions)

    origin_root_recipe = recipe.root_recipe or recipe
    origin_parent_recipe = recipe.parent
    if recipe.is_master and recipe.test_sequence is None and recipe.recipe_group_id:
        origin_parent_recipe = (
            Recipe.query.filter(
                Recipe.recipe_group_id == recipe.recipe_group_id,
                Recipe.is_master.is_(True),
                Recipe.test_sequence.is_(None),
                Recipe.version_number < recipe.version_number,
            )
            .order_by(Recipe.version_number.desc())
            .first()
        )
    events_page = request.args.get("events_page", 1, type=int) or 1
    if events_page < 1:
        events_page = 1
    events_pagination = (
        RecipeLineage.query.options(
            selectinload(RecipeLineage.source_recipe)
        )
        .filter_by(recipe_id=recipe.id)
        .order_by(RecipeLineage.created_at.desc())
        .paginate(page=events_page, per_page=10, error_out=False)
    )
    events = events_pagination.items

    origin_source_org = None
    if recipe.org_origin_purchased and recipe.org_origin_source_org:
        origin_source_org = recipe.org_origin_source_org

    origin_marketplace_enabled = False
    if origin_source_org:
        origin_marketplace_enabled = _org_tier_includes_permission(
            origin_source_org, "recipes.marketplace_dashboard"
        )
    show_origin_marketplace = (
        is_feature_enabled("FEATURE_RECIPE_MARKETPLACE_DISPLAY")
        and origin_marketplace_enabled
        and has_permission(current_user, "recipes.marketplace_dashboard")
    )

    return render_template(
        'pages/recipes/recipe_lineage.html',
        recipe=recipe,
        origin_source_org=origin_source_org,
        lineage_tree=lineage_tree,
        lineage_path=lineage_path,
        lineage_events=events,
        lineage_events_pagination=events_pagination,
        show_origin_marketplace=show_origin_marketplace,
        master_branches=master_branches,
        variation_branches=variation_branches,
        origin_root_recipe=origin_root_recipe,
        origin_parent_recipe=origin_parent_recipe,
    )
