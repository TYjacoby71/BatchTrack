"""Lineage and label generation service.

Synopsis:
Generates recipe group, label, and variation prefixes plus lineage IDs and batch labels.
Lineage IDs use organization-scoped group sequencing to stay stable within a tenant.

Glossary:
- Prefix: Short code derived from a name for labels.
- Label prefix: Recipe-level prefix used in batch labels.
- Lineage ID: Dot-notation identifier for version history.
- Group number: Organization-scoped sequence for recipe groups.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

import sqlalchemy as sa

from app.extensions import db
from app.models.recipe import Recipe, RecipeGroup


# --- Clean and split ---
# Purpose: Normalize and split a name into words.
def _clean_and_split(name: str) -> List[str]:
    if not name:
        return []
    cleaned = re.sub(r"[^A-Za-z0-9\s]+", " ", str(name))
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    return [word for word in cleaned.split() if word]


# --- Prefix candidates ---
# Purpose: Build candidate prefixes from words.
def _build_prefix_candidates(words: List[str]) -> List[str]:
    if not words:
        return ["RCP"]

    upper_words = [word.upper() for word in words]
    candidates: List[str] = []

    if len(upper_words) == 1:
        candidates.append(upper_words[0][:3])
        candidates.append(upper_words[0][:4])
    elif len(upper_words) == 2:
        candidates.append((upper_words[0][:2] + upper_words[1][:1]))
        candidates.append((upper_words[0][:1] + upper_words[1][:2]))
    else:
        candidates.append((upper_words[0][:1] + upper_words[1][:1] + upper_words[2][:1]))
        candidates.append((upper_words[0][:1] + upper_words[1][:2] + upper_words[2][:1]))

    # Ensure consistent casing and non-empty
    normalized = [candidate for candidate in (c.upper().strip() for c in candidates) if candidate]
    return normalized or ["RCP"]


# --- Resolve prefixes ---
# Purpose: Normalize existing prefixes for comparison.
def _resolve_existing_prefixes(prefixes: Iterable[str] | None) -> Set[str]:
    if not prefixes:
        return set()
    return {str(prefix).upper() for prefix in prefixes if prefix}


# --- Pick unique prefix ---
# Purpose: Choose a unique prefix from candidates.
def _pick_unique_prefix(candidates: List[str], existing: Set[str]) -> str:
    for candidate in candidates:
        if candidate not in existing:
            return candidate

    base = candidates[0] if candidates else "RCP"
    index = 1
    while True:
        candidate = f"{base}{index}"
        if candidate not in existing:
            return candidate
        index += 1


# --- Generate group prefix ---
# Purpose: Generate a unique group prefix per organization.
def generate_group_prefix(name: str, org_id: int | None) -> str:
    words = _clean_and_split(name)
    candidates = _build_prefix_candidates(words)
    existing: Set[str] = set()
    if org_id:
        existing = _resolve_existing_prefixes(
            row[0] for row in db.session.query(RecipeGroup.prefix).filter(
                RecipeGroup.organization_id == org_id
            )
        )
    return _pick_unique_prefix(candidates, existing)


# --- Generate variation prefix ---
# Purpose: Generate a unique variation prefix per group.
def generate_variation_prefix(name: str, recipe_group_id: int | None) -> str:
    words = _clean_and_split(name)
    candidates = _build_prefix_candidates(words)
    existing: Set[str] = set()
    if recipe_group_id:
        existing = _resolve_existing_prefixes(
            row[0] for row in db.session.query(Recipe.variation_prefix).filter(
                Recipe.recipe_group_id == recipe_group_id,
                Recipe.variation_prefix.isnot(None),
            )
        )
    return _pick_unique_prefix(candidates, existing)


# --- Generate label prefix ---
# Purpose: Generate a unique label prefix per organization.
def generate_label_prefix(name: str, org_id: int | None) -> str:
    words = _clean_and_split(name)
    candidates = _build_prefix_candidates(words)
    existing: Set[str] = set()
    if org_id:
        existing = _resolve_existing_prefixes(
            row[0]
            for row in db.session.query(RecipeGroup.prefix)
            .filter(RecipeGroup.organization_id == org_id)
        )
        existing.update(
            _resolve_existing_prefixes(
                row[0]
                for row in db.session.query(Recipe.label_prefix)
                .filter(
                    Recipe.organization_id == org_id,
                    Recipe.label_prefix.isnot(None),
                )
            )
        )
    return _pick_unique_prefix(candidates, existing)


# --- Resolve group number ---
# Purpose: Map recipe_group_id to org-scoped sequence number.
def _resolve_group_number(version_obj: Recipe) -> int:
    group_id = getattr(version_obj, "recipe_group_id", None)
    if not group_id:
        return 0
    org_id = getattr(version_obj, "organization_id", None)
    if not org_id:
        group = getattr(version_obj, "recipe_group", None)
        org_id = getattr(group, "organization_id", None) if group else None
    if not org_id:
        return int(group_id)
    count = (
        db.session.query(sa.func.count(RecipeGroup.id))
        .filter(
            RecipeGroup.organization_id == org_id,
            RecipeGroup.id <= group_id,
        )
        .scalar()
    )
    resolved = int(count or 0)
    return resolved if resolved > 0 else int(group_id)


# --- Generate lineage ID ---
# Purpose: Generate a lineage ID for a recipe version.
def generate_lineage_id(version_obj: Recipe) -> str:
    group_number = _resolve_group_number(version_obj)
    is_master = getattr(version_obj, "is_master", False)
    if is_master:
        master_version = getattr(version_obj, "version_number", None) or 0
    else:
        parent_master = getattr(version_obj, "parent_master", None)
        master_version = getattr(parent_master, "version_number", None) if parent_master else None
        master_version = master_version or getattr(version_obj, "version_number", None) or 0

    parts = [str(group_number), str(master_version)]
    if not is_master:
        variation_version = getattr(version_obj, "version_number", None) or 0
        parts.append(str(variation_version))

    test_sequence = getattr(version_obj, "test_sequence", None)
    if test_sequence:
        parts.append(f"t{test_sequence}")

    return ".".join(parts)


# --- Generate batch label ---
# Purpose: Generate a human-readable batch label.
def generate_batch_label(version_obj: Recipe, year: int, seq_num: int) -> str:
    group = getattr(version_obj, "recipe_group", None)
    group_prefix = getattr(group, "prefix", None)
    if not group_prefix:
        group_prefix = getattr(version_obj, "label_prefix", None) or ""
    if not group_prefix:
        group_prefix = _build_prefix_candidates(_clean_and_split(getattr(version_obj, "name", "") or ""))[0]
    group_prefix = group_prefix.upper()

    if getattr(version_obj, "is_master", False):
        master_version = getattr(version_obj, "version_number", None) or 0
    else:
        parent_master = getattr(version_obj, "parent_master", None)
        master_version = getattr(parent_master, "version_number", None) if parent_master else None
        master_version = master_version or getattr(version_obj, "version_number", None) or 0

    label = f"{group_prefix}{master_version}"

    if not getattr(version_obj, "is_master", False):
        var_prefix = getattr(version_obj, "variation_prefix", None)
        if not var_prefix:
            var_prefix = _build_prefix_candidates(
                _clean_and_split(getattr(version_obj, "variation_name", "") or getattr(version_obj, "name", "") or "")
            )[0]
        var_prefix = var_prefix.upper()
        var_version = getattr(version_obj, "version_number", None) or 0
        label += f"-{var_prefix}{var_version}"

    test_sequence = getattr(version_obj, "test_sequence", None)
    if test_sequence:
        label += f"-T{test_sequence}"

    label += f"-{year}-{int(seq_num):03d}"
    return label


# --- Format label prefix for display ---
# Purpose: Build a lineage-aware label prefix string for UI.
def format_label_prefix(
    version_obj: Recipe,
    *,
    test_sequence: int | None = None,
    include_master_version_for_master: bool = False,
) -> str:
    group = getattr(version_obj, "recipe_group", None)
    resolved_test = test_sequence if test_sequence is not None else getattr(version_obj, "test_sequence", None)
    is_master = bool(getattr(version_obj, "is_master", False))

    master_source = version_obj
    if not is_master:
        master_source = getattr(version_obj, "parent_master", None) or version_obj

    base_prefix = (
        getattr(master_source, "label_prefix", None)
        or getattr(group, "prefix", None)
        or getattr(version_obj, "label_prefix", None)
        or ""
    )
    if not base_prefix:
        base_prefix = _build_prefix_candidates(
            _clean_and_split(getattr(version_obj, "name", "") or "")
        )[0]
    base_prefix = str(base_prefix).upper()
    if is_master and not resolved_test and not include_master_version_for_master:
        return base_prefix

    if is_master:
        master_version = getattr(version_obj, "version_number", None) or 0
    else:
        parent_master = getattr(version_obj, "parent_master", None)
        master_version = getattr(parent_master, "version_number", None) if parent_master else None
        master_version = master_version or getattr(version_obj, "version_number", None) or 0

    label = f"{base_prefix}{master_version}"

    if not is_master:
        var_prefix = getattr(version_obj, "variation_prefix", None)
        if not var_prefix:
            var_prefix = _build_prefix_candidates(
                _clean_and_split(
                    getattr(version_obj, "variation_name", "")
                    or getattr(version_obj, "name", "")
                    or ""
                )
            )[0]
        var_prefix = str(var_prefix).upper()
        var_version = getattr(version_obj, "version_number", None) or 0
        label += f"-{var_prefix}{var_version}"

    if resolved_test:
        label += f"-T{resolved_test}"

    return label


__all__ = [
    "generate_group_prefix",
    "generate_label_prefix",
    "generate_variation_prefix",
    "generate_lineage_id",
    "generate_batch_label",
    "format_label_prefix",
]
