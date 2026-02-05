"""Backfill recipe lineage group and batch lineage data.

Synopsis:
Backfills recipe groups, version defaults, and batch lineage references.

Glossary:
- Recipe group: Container for master/variation lineages.
- Current version: Latest published recipe per branch.
"""
from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0021_recipe_lineage_backfill"
down_revision = "0020_recipe_current_flag"
branch_labels = None
depends_on = None


def _resolve_root_id(recipe_id: int, recipes: dict[int, dict], seen: set[int]) -> int:
    if recipe_id in seen:
        return recipe_id
    seen.add(recipe_id)
    recipe = recipes.get(recipe_id)
    if not recipe:
        return recipe_id
    root_id = recipe.get("root_recipe_id")
    if root_id:
        return int(root_id)
    parent_id = recipe.get("parent_recipe_id")
    if parent_id:
        return _resolve_root_id(int(parent_id), recipes, seen)
    return recipe_id


def _next_prefix(org_id: int, existing: dict[int, set[str]], counters: dict[int, int]) -> str:
    prefix_set = existing.setdefault(org_id, set())
    counter = counters.get(org_id, 1)
    while True:
        candidate = f"RG{counter:06d}"
        if candidate not in prefix_set:
            prefix_set.add(candidate)
            counters[org_id] = counter + 1
            return candidate
        counter += 1


def _compute_lineage_id(recipe: dict, recipes: dict[int, dict]) -> str:
    group_id = int(recipe.get("recipe_group_id") or 0)
    is_master = bool(recipe.get("is_master"))
    version_number = int(recipe.get("version_number") or 0)
    test_sequence = recipe.get("test_sequence")
    if is_master:
        master_version = version_number
    else:
        parent_master_id = recipe.get("parent_master_id")
        parent_master = recipes.get(parent_master_id) if parent_master_id else None
        master_version = int(parent_master.get("version_number") or 0) if parent_master else version_number
    var_version = 0 if is_master else version_number
    test_suffix = f"t{int(test_sequence)}" if test_sequence else ""
    return f"{group_id}.{master_version}.{var_version}{test_suffix}"


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(
        bind=bind,
        only=(
            "recipe",
            "recipe_group",
            "batch",
            "inventory_history",
            "unified_inventory_history",
        ),
    )
    recipe_tbl = sa.Table("recipe", meta, autoload_with=bind)
    recipe_group_tbl = sa.Table("recipe_group", meta, autoload_with=bind)
    batch_tbl = sa.Table("batch", meta, autoload_with=bind)
    inv_hist_tbl = sa.Table("inventory_history", meta, autoload_with=bind)
    unified_hist_tbl = sa.Table("unified_inventory_history", meta, autoload_with=bind)

    now = datetime.utcnow()

    group_rows = list(
        bind.execute(
            sa.select(
                recipe_group_tbl.c.id,
                recipe_group_tbl.c.organization_id,
                recipe_group_tbl.c.prefix,
            )
        )
    )
    existing_prefixes: dict[int, set[str]] = {}
    for row in group_rows:
        existing_prefixes.setdefault(int(row.organization_id), set()).add(str(row.prefix or "").upper())

    recipe_rows = list(
        bind.execute(
            sa.select(
                recipe_tbl.c.id,
                recipe_tbl.c.organization_id,
                recipe_tbl.c.name,
                recipe_tbl.c.label_prefix,
                recipe_tbl.c.parent_recipe_id,
                recipe_tbl.c.root_recipe_id,
                recipe_tbl.c.recipe_group_id,
                recipe_tbl.c.variation_name,
                recipe_tbl.c.version_number,
                recipe_tbl.c.parent_master_id,
                recipe_tbl.c.test_sequence,
                recipe_tbl.c.is_master,
                recipe_tbl.c.status,
                recipe_tbl.c.is_archived,
                recipe_tbl.c.created_at,
            )
        )
    )
    recipes: dict[int, dict] = {int(row.id): dict(row._mapping) for row in recipe_rows}

    root_map: dict[int, int] = {}
    for recipe_id in recipes:
        root_map[recipe_id] = _resolve_root_id(recipe_id, recipes, set())

    root_group_map: dict[int, int] = {}
    for recipe_id, recipe in recipes.items():
        group_id = recipe.get("recipe_group_id")
        if group_id:
            root_group_map.setdefault(root_map[recipe_id], int(group_id))

    prefix_counters: dict[int, int] = {}
    created_group_ids: set[int] = set()

    for recipe_id, recipe in recipes.items():
        if recipe.get("recipe_group_id"):
            continue
        root_id = root_map[recipe_id]
        if root_id in root_group_map:
            continue
        root_recipe = recipes.get(root_id) or recipe
        org_id = int(root_recipe.get("organization_id") or 0)
        group_name = (root_recipe.get("name") or f"Recipe Group {root_id}").strip()
        label_prefix = (root_recipe.get("label_prefix") or "").strip().upper()
        prefix = None
        if label_prefix:
            candidate = label_prefix[:8]
            if candidate and candidate not in existing_prefixes.setdefault(org_id, set()):
                prefix = candidate
                existing_prefixes[org_id].add(candidate)
        if not prefix:
            prefix = _next_prefix(org_id, existing_prefixes, prefix_counters)

        result = bind.execute(
            recipe_group_tbl.insert().values(
                organization_id=org_id,
                name=group_name,
                prefix=prefix,
                created_at=now,
                updated_at=now,
            )
        )
        group_id = int(result.inserted_primary_key[0])
        root_group_map[root_id] = group_id
        created_group_ids.add(group_id)

    backfill_ids: list[int] = []
    for recipe_id, recipe in recipes.items():
        if recipe.get("recipe_group_id"):
            continue
        group_id = root_group_map.get(root_map[recipe_id])
        if not group_id:
            continue
        is_master = recipe_id == root_map[recipe_id]
        update_values = {
            "recipe_group_id": group_id,
            "is_master": is_master,
        }
        if not is_master:
            if not recipe.get("variation_name"):
                update_values["variation_name"] = (recipe.get("name") or "Variation").strip()
            if not recipe.get("parent_master_id"):
                update_values["parent_master_id"] = root_map[recipe_id]
        bind.execute(
            recipe_tbl.update().where(recipe_tbl.c.id == recipe_id).values(**update_values)
        )
        recipe.update(update_values)
        backfill_ids.append(recipe_id)

    branch_map: dict[tuple, list[dict]] = {}
    for recipe_id in backfill_ids:
        recipe = recipes[recipe_id]
        branch_key = (
            recipe.get("recipe_group_id"),
            bool(recipe.get("is_master")),
            recipe.get("variation_name"),
        )
        branch_map.setdefault(branch_key, []).append(recipe)

    for branch_key, branch_recipes in branch_map.items():
        branch_sorted = sorted(
            branch_recipes,
            key=lambda r: (r.get("created_at") or now, r.get("id")),
        )
        version = 1
        for recipe in branch_sorted:
            if recipe.get("test_sequence"):
                continue
            bind.execute(
                recipe_tbl.update()
                .where(recipe_tbl.c.id == int(recipe["id"]))
                .values(version_number=version)
            )
            recipe["version_number"] = version
            version += 1

    for branch_key, branch_recipes in branch_map.items():
        group_id = branch_key[0]
        if group_id not in created_group_ids:
            continue
        candidates = [
            recipe for recipe in branch_recipes
            if not recipe.get("test_sequence")
            and recipe.get("status") == "published"
            and not recipe.get("is_archived")
        ]
        if not candidates:
            continue
        chosen = max(candidates, key=lambda r: (int(r.get("version_number") or 0), int(r.get("id"))))
        for recipe in branch_recipes:
            bind.execute(
                recipe_tbl.update()
                .where(recipe_tbl.c.id == int(recipe["id"]))
                .values(is_current=(recipe["id"] == chosen["id"]))
            )

    batch_rows = list(
        bind.execute(
            sa.select(
                batch_tbl.c.id,
                batch_tbl.c.recipe_id,
                batch_tbl.c.target_version_id,
                batch_tbl.c.lineage_id,
            )
        )
    )
    batch_lineage_map: dict[int, str] = {}
    for batch in batch_rows:
        batch_id = int(batch.id)
        target_id = batch.target_version_id or batch.recipe_id
        if target_id:
            target_id = int(target_id)
        if batch.target_version_id is None and target_id:
            bind.execute(
                batch_tbl.update()
                .where(batch_tbl.c.id == batch_id)
                .values(target_version_id=target_id)
            )
        if batch.lineage_id or not target_id:
            continue
        recipe = recipes.get(target_id)
        if not recipe or not recipe.get("recipe_group_id"):
            continue
        lineage_id = _compute_lineage_id(recipe, recipes)
        bind.execute(
            batch_tbl.update()
            .where(batch_tbl.c.id == batch_id)
            .values(lineage_id=lineage_id)
        )
        batch_lineage_map[batch_id] = lineage_id

    if not batch_lineage_map:
        batch_lineage_map = {
            int(row.id): str(row.lineage_id)
            for row in bind.execute(
                sa.select(batch_tbl.c.id, batch_tbl.c.lineage_id)
                .where(batch_tbl.c.lineage_id.isnot(None))
            )
        }

    def _backfill_history(table: sa.Table) -> None:
        rows = list(
            bind.execute(
                sa.select(
                    table.c.id,
                    table.c.batch_id,
                    table.c.used_for_batch_id,
                    table.c.lineage_id,
                ).where(
                    table.c.lineage_id.is_(None),
                    sa.or_(table.c.batch_id.isnot(None), table.c.used_for_batch_id.isnot(None)),
                )
            )
        )
        for row in rows:
            batch_id = row.batch_id or row.used_for_batch_id
            if not batch_id:
                continue
            lineage_id = batch_lineage_map.get(int(batch_id))
            if lineage_id:
                bind.execute(
                    table.update()
                    .where(table.c.id == int(row.id))
                    .values(lineage_id=lineage_id)
                )

    _backfill_history(inv_hist_tbl)
    _backfill_history(unified_hist_tbl)


def downgrade():
    # No-op: backfill is not reversible.
    pass
