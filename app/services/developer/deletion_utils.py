from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from flask import current_app, has_app_context
from sqlalchemy import Table, inspect as sa_inspect, or_

from app.extensions import db
from app.models import Recipe
from app.models.recipe import RecipeLineage
from app.utils.json_store import write_json_file

logger = logging.getLogger(__name__)


def _normalize_ids(values: Sequence[int] | Iterable[int] | None) -> list[int]:
    normalized: list[int] = []
    for value in values or []:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            normalized.append(parsed)
    return sorted(set(normalized))


def _archive_directory() -> Path:
    if has_app_context():
        configured = current_app.config.get("DELETION_ARCHIVE_DIR")
        if configured:
            return Path(configured)
    return Path("data/deletion_archives")


def _to_iso(value) -> str | None:
    return value.isoformat() if value else None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_table(table_name: str):
    table = db.metadata.tables.get(table_name)
    if table is not None:
        return table
    return Table(table_name, db.metadata, autoload_with=db.engine)


def _serialize_recipe_snapshot(recipe: Recipe) -> dict:
    ingredient_rows = []
    for row in recipe.recipe_ingredients or []:
        item = getattr(row, "inventory_item", None)
        ingredient_rows.append(
            {
                "inventory_item_id": row.inventory_item_id,
                "inventory_item_name": getattr(item, "name", None),
                "global_item_id": getattr(item, "global_item_id", None),
                "quantity": _to_float(row.quantity),
                "unit": row.unit,
            }
        )

    consumable_rows = []
    for row in recipe.recipe_consumables or []:
        item = getattr(row, "inventory_item", None)
        consumable_rows.append(
            {
                "inventory_item_id": row.inventory_item_id,
                "inventory_item_name": getattr(item, "name", None),
                "global_item_id": getattr(item, "global_item_id", None),
                "quantity": _to_float(row.quantity),
                "unit": row.unit,
            }
        )

    return {
        "legacy_key": f"org-{recipe.organization_id}-recipe-{recipe.id}",
        "id": recipe.id,
        "organization_id": recipe.organization_id,
        "name": recipe.name,
        "status": recipe.status,
        "sharing_scope": recipe.sharing_scope,
        "marketplace_status": recipe.marketplace_status,
        "is_public": bool(recipe.is_public),
        "is_for_sale": bool(recipe.is_for_sale),
        "is_sellable": bool(getattr(recipe, "is_sellable", True)),
        "sale_price": _to_float(recipe.sale_price),
        "purchase_count": int(recipe.purchase_count or 0),
        "download_count": int(recipe.download_count or 0),
        "public_description": recipe.public_description,
        "marketplace_notes": recipe.marketplace_notes,
        "instructions": recipe.instructions,
        "predicted_yield": _to_float(recipe.predicted_yield),
        "predicted_yield_unit": recipe.predicted_yield_unit,
        "created_at": _to_iso(recipe.created_at),
        "updated_at": _to_iso(recipe.updated_at),
        "ingredients": ingredient_rows,
        "consumables": consumable_rows,
    }


def archive_marketplace_recipes(organization, recipes: Sequence[Recipe]) -> str | None:
    candidates = [
        recipe
        for recipe in (recipes or [])
        if (
            bool(recipe.is_public)
            or bool(recipe.is_for_sale)
            or recipe.marketplace_status == "listed"
            or int(recipe.purchase_count or 0) > 0
            or int(recipe.download_count or 0) > 0
        )
    ]
    if not candidates:
        return None

    archive_dir = _archive_directory()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"org_{organization.id}_marketplace_recipes_{timestamp}.json"

    payload = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "contact_email": getattr(organization, "contact_email", None),
        },
        "recipe_count": len(candidates),
        "recipes": [_serialize_recipe_snapshot(recipe) for recipe in candidates],
    }
    write_json_file(archive_path, payload)
    return str(archive_path)


def detach_external_recipe_links(
    deleted_org_id: int,
    deleted_recipe_ids: Sequence[int],
    *,
    archive_path: str | None = None,
) -> int:
    recipe_ids = _normalize_ids(deleted_recipe_ids)
    if not recipe_ids:
        return 0

    touched = 0
    external_recipes = (
        Recipe.query.filter(
            or_(Recipe.organization_id.is_(None), Recipe.organization_id != deleted_org_id),
            or_(
                Recipe.origin_organization_id == deleted_org_id,
                Recipe.origin_recipe_id.in_(recipe_ids),
                Recipe.org_origin_source_org_id == deleted_org_id,
                Recipe.org_origin_source_recipe_id.in_(recipe_ids),
                Recipe.parent_recipe_id.in_(recipe_ids),
                Recipe.parent_master_id.in_(recipe_ids),
                Recipe.cloned_from_id.in_(recipe_ids),
                Recipe.root_recipe_id.in_(recipe_ids),
            ),
        )
        .all()
    )

    for recipe in external_recipes:
        changed = False
        if recipe.origin_organization_id == deleted_org_id:
            recipe.origin_organization_id = None
            changed = True
        if recipe.origin_recipe_id in recipe_ids:
            recipe.origin_recipe_id = None
            changed = True
        if recipe.org_origin_source_org_id == deleted_org_id:
            recipe.org_origin_source_org_id = None
            changed = True
        if recipe.org_origin_source_recipe_id in recipe_ids:
            recipe.org_origin_source_recipe_id = None
            changed = True
        if recipe.parent_recipe_id in recipe_ids:
            recipe.parent_recipe_id = None
            changed = True
        if recipe.parent_master_id in recipe_ids:
            recipe.parent_master_id = None
            changed = True
        if recipe.cloned_from_id in recipe_ids:
            recipe.cloned_from_id = None
            changed = True
        if recipe.root_recipe_id in recipe_ids:
            recipe.root_recipe_id = recipe.id
            changed = True

        if changed:
            touched += 1
            if archive_path:
                logger.info(
                    "Detached legacy source links for recipe %s using archive %s",
                    recipe.id,
                    archive_path,
                )

    lineage_rows = RecipeLineage.query.filter(
        or_(RecipeLineage.organization_id.is_(None), RecipeLineage.organization_id != deleted_org_id),
        RecipeLineage.source_recipe_id.in_(recipe_ids),
    ).all()
    for event in lineage_rows:
        event.source_recipe_id = None
        touched += 1

    return touched


def _topological_child_first(nodes: Sequence[str], dependencies: dict[str, set[str]]) -> list[str]:
    node_set = set(nodes)
    indegree = {node: 0 for node in node_set}
    adjacency: dict[str, set[str]] = {node: set() for node in node_set}

    for child, parents in dependencies.items():
        if child not in node_set:
            continue
        for parent in parents:
            if parent not in node_set or parent == child:
                continue
            adjacency[child].add(parent)
            indegree[parent] += 1

    queue = deque(sorted(node for node, count in indegree.items() if count == 0))
    ordered: list[str] = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for parent in sorted(adjacency[node]):
            indegree[parent] -= 1
            if indegree[parent] == 0:
                queue.append(parent)

    if len(ordered) != len(node_set):
        remaining = sorted(node_set.difference(ordered))
        ordered.extend(remaining)

    return ordered


def delete_org_scoped_rows(org_id: int, *, exclude_tables: set[str] | None = None) -> list[str]:
    exclude = set(exclude_tables or set())
    inspector = sa_inspect(db.engine)

    candidate_tables: list[str] = []
    fk_lookup: dict[str, set[str]] = {}
    for table_name in inspector.get_table_names():
        if table_name in exclude or table_name == "organization":
            continue

        columns = inspector.get_columns(table_name)
        if not any(column.get("name") == "organization_id" for column in columns):
            continue

        candidate_tables.append(table_name)
        fk_lookup[table_name] = {
            fk.get("referred_table")
            for fk in inspector.get_foreign_keys(table_name)
            if fk.get("referred_table")
        }

    ordered = _topological_child_first(candidate_tables, fk_lookup)
    deleted_tables: list[str] = []
    for table_name in ordered:
        table = _resolve_table(table_name)
        if "organization_id" not in table.c:
            continue
        db.session.execute(table.delete().where(table.c.organization_id == org_id))
        deleted_tables.append(table_name)

    return deleted_tables


def clear_user_foreign_keys(user_ids: Sequence[int]) -> None:
    ids = _normalize_ids(user_ids)
    if not ids:
        return

    inspector = sa_inspect(db.engine)
    for table_name in inspector.get_table_names():
        table = _resolve_table(table_name)

        column_info = {column["name"]: column for column in inspector.get_columns(table_name)}
        nullable_columns: list[str] = []
        non_nullable_columns: list[str] = []

        for fk in inspector.get_foreign_keys(table_name):
            if fk.get("referred_table") != "user":
                continue
            for column_name in fk.get("constrained_columns") or []:
                info = column_info.get(column_name)
                if not info or column_name not in table.c:
                    continue
                if info.get("nullable", True):
                    nullable_columns.append(column_name)
                else:
                    non_nullable_columns.append(column_name)

        for column_name in sorted(set(non_nullable_columns)):
            column = table.c[column_name]
            db.session.execute(table.delete().where(column.in_(ids)))

        for column_name in sorted(set(nullable_columns)):
            column = table.c[column_name]
            db.session.execute(
                table.update().where(column.in_(ids)).values({column_name: None})
            )


__all__ = [
    "archive_marketplace_recipes",
    "clear_user_foreign_keys",
    "delete_org_scoped_rows",
    "detach_external_recipe_links",
]
