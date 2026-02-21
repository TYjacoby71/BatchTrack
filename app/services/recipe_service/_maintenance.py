"""Recipe maintenance helpers.

Synopsis:
Utilities for repairing legacy test numbering and names.

Glossary:
- Test scope: A unique lineage bucket where test numbering starts at 1.
  * Master tests: recipe_group + master version
  * Variation tests: recipe_group + variation name + variation version
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy.orm import selectinload

from ...extensions import db
from ...models import Recipe

_TEST_SUFFIX_PATTERN = re.compile(r"\s*-\s*test\s+\d+\s*$", re.IGNORECASE)


def _strip_test_suffix(value: str | None) -> str:
    if not value:
        return ""
    return _TEST_SUFFIX_PATTERN.sub("", value).strip()


def _variation_bucket_name(recipe: Recipe) -> str:
    candidate = (recipe.variation_name or "").strip()
    if candidate:
        return candidate.lower()

    parent = getattr(recipe, "parent", None)
    if parent:
        parent_candidate = (
            getattr(parent, "variation_name", None) or getattr(parent, "name", None) or ""
        ).strip()
        if parent_candidate:
            return parent_candidate.lower()

    # Defensive fallback keeps otherwise-unscoped rows from collapsing together.
    return f"variation-{int(recipe.parent_master_id or recipe.parent_recipe_id or recipe.id)}"


def _test_scope_key(recipe: Recipe) -> Tuple[Any, ...]:
    group_id = getattr(recipe, "recipe_group_id", None)
    root_id = getattr(recipe, "root_recipe_id", None)
    version_number = int(getattr(recipe, "version_number", 0) or 0)
    if getattr(recipe, "is_master", False):
        return ("master", group_id, root_id, version_number)
    return ("variation", group_id, root_id, _variation_bucket_name(recipe), version_number)


def _base_test_name(recipe: Recipe) -> str:
    if getattr(recipe, "is_master", False):
        group = getattr(recipe, "recipe_group", None)
        return (
            (getattr(group, "name", None) or "").strip()
            or _strip_test_suffix(getattr(recipe, "name", None))
            or "Recipe"
        )

    variation_name = (
        (getattr(recipe, "variation_name", None) or "").strip()
        or (
            (
                getattr(getattr(recipe, "parent", None), "variation_name", None)
                or getattr(getattr(recipe, "parent", None), "name", None)
                or ""
            ).strip()
        )
        or _strip_test_suffix(getattr(recipe, "name", None))
        or "Variation"
    )
    return variation_name.rstrip("-").strip()


def _created_sort_key(recipe: Recipe) -> Tuple[str, int]:
    created_at = getattr(recipe, "created_at", None)
    created_token = created_at.isoformat() if isinstance(created_at, datetime) else ""
    return created_token, int(getattr(recipe, "id", 0) or 0)


@dataclass
class _RepairCounters:
    scanned: int = 0
    buckets: int = 0
    sequence_updates: int = 0
    renamed: int = 0

    @property
    def total_changes(self) -> int:
        return self.sequence_updates + self.renamed


def repair_test_sequences(
    *,
    organization_id: int | None = None,
    recipe_group_id: int | None = None,
    apply_changes: bool = False,
    preview_limit: int = 25,
) -> Dict[str, Any]:
    """Repair test numbering and names to match lineage scope.

    When apply_changes is False, this function performs a dry run.
    """
    query = Recipe.query.options(
        selectinload(Recipe.recipe_group),
        selectinload(Recipe.parent),
    ).filter(Recipe.test_sequence.isnot(None))

    if organization_id is not None:
        query = query.filter(Recipe.organization_id == organization_id)
    if recipe_group_id is not None:
        query = query.filter(Recipe.recipe_group_id == recipe_group_id)

    tests = query.order_by(
        Recipe.recipe_group_id.asc().nullsfirst(),
        Recipe.is_master.desc(),
        Recipe.variation_name.asc().nullsfirst(),
        Recipe.version_number.asc(),
        Recipe.created_at.asc().nullsfirst(),
        Recipe.id.asc(),
    ).all()

    buckets: Dict[Tuple[Any, ...], List[Recipe]] = defaultdict(list)
    for recipe in tests:
        buckets[_test_scope_key(recipe)].append(recipe)

    counters = _RepairCounters(scanned=len(tests), buckets=len(buckets))
    preview: List[Dict[str, Any]] = []

    for scope_key, scoped_tests in buckets.items():
        scoped_tests.sort(key=_created_sort_key)
        for expected_sequence, recipe in enumerate(scoped_tests, start=1):
            old_sequence = int(getattr(recipe, "test_sequence", 0) or 0)
            expected_name = f"{_base_test_name(recipe)} - Test {expected_sequence}"
            old_name = (getattr(recipe, "name", None) or "").strip()

            sequence_changed = old_sequence != expected_sequence
            name_changed = old_name != expected_name
            if not (sequence_changed or name_changed):
                continue

            if sequence_changed:
                counters.sequence_updates += 1
            if name_changed:
                counters.renamed += 1

            if len(preview) < max(0, int(preview_limit)):
                preview.append(
                    {
                        "recipe_id": int(recipe.id),
                        "scope": scope_key,
                        "old_sequence": old_sequence,
                        "new_sequence": expected_sequence,
                        "old_name": old_name,
                        "new_name": expected_name,
                    }
                )

            if apply_changes:
                recipe.test_sequence = expected_sequence
                recipe.name = expected_name

    if apply_changes and counters.total_changes:
        db.session.commit()
    else:
        db.session.rollback()

    return {
        "scanned": counters.scanned,
        "buckets": counters.buckets,
        "sequence_updates": counters.sequence_updates,
        "renamed": counters.renamed,
        "total_changes": counters.total_changes,
        "applied": bool(apply_changes),
        "preview": preview,
    }


__all__ = ["repair_test_sequences"]
