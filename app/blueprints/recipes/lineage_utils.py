"""Lineage utilities for recipe trees.

Synopsis:
Serializes lineage trees and builds navigation paths.

Glossary:
- Lineage tree: Hierarchy of versions, variations, and clones.
- Current node: Version flagged as current for a branch.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.models import Recipe


# --- Serialize lineage tree ---
# Purpose: Build a lineage tree payload for UI rendering.
def serialize_lineage_tree(node_recipe: Recipe, nodes: Dict[int, dict]) -> dict:
    node_payload = {
        'id': node_recipe.id,
        'name': node_recipe.name,
        'organization_name': node_recipe.organization.name if node_recipe.organization else None,
        'organization_id': node_recipe.organization_id,
        'origin_type': node_recipe.org_origin_type,
        'origin_purchased': node_recipe.org_origin_purchased,
        'is_current': bool(getattr(node_recipe, "is_current", False)),
        'test_sequence': getattr(node_recipe, "test_sequence", None),
        'is_master': bool(getattr(node_recipe, "is_master", False)),
        'status': node_recipe.status,
        'children': [],
    }

    for child in nodes.get(node_recipe.id, {}).get('children', []):
        child_recipe = nodes[child['id']]['recipe']
        node_payload['children'].append(
            {
                'edge_type': child['edge'],
                'node': serialize_lineage_tree(child_recipe, nodes),
            }
        )

    return node_payload


# --- Build lineage path ---
# Purpose: Build a path list from root to selected node.
def build_lineage_path(target_id: int, nodes: Dict[int, dict], root_id: Optional[int]) -> List[int]:
    path: List[int] = []
    seen: set[int] = set()
    current_id = target_id

    while current_id and current_id not in seen:
        path.append(current_id)
        seen.add(current_id)
        recipe = nodes.get(current_id, {}).get('recipe')
        if not recipe:
            break
        if recipe.parent_recipe_id and recipe.parent_recipe_id in nodes:
            current_id = recipe.parent_recipe_id
        elif recipe.cloned_from_id and recipe.cloned_from_id in nodes:
            current_id = recipe.cloned_from_id
        elif (
            recipe.root_recipe_id
            and recipe.root_recipe_id in nodes
            and recipe.id != recipe.root_recipe_id
        ):
            current_id = recipe.root_recipe_id
        else:
            current_id = None

    if root_id and root_id not in path:
        path.append(root_id)

    return list(reversed(path))


# --- Build version branches ---
# Purpose: Group masters/variations with their tests for UI.
def build_version_branches(recipes: List[Recipe]) -> Tuple[List[dict], List[dict]]:
    masters = [
        r for r in recipes
        if getattr(r, "is_master", False) and getattr(r, "test_sequence", None) is None
    ]
    masters.sort(key=lambda r: int(getattr(r, "version_number", 0) or 0), reverse=True)

    master_tests = [
        r for r in recipes
        if getattr(r, "is_master", False) and getattr(r, "test_sequence", None) is not None
    ]
    master_tests_by_parent: Dict[int, List[Recipe]] = {}
    for test in master_tests:
        parent_id = getattr(test, "parent_recipe_id", None) or getattr(test, "parent_master_id", None)
        if parent_id:
            master_tests_by_parent.setdefault(int(parent_id), []).append(test)
    for tests in master_tests_by_parent.values():
        tests.sort(key=lambda r: int(getattr(r, "test_sequence", 0) or 0))

    master_branches: List[dict] = [
        {
            "version": master,
            "tests": master_tests_by_parent.get(master.id, []),
        }
        for master in masters
    ]

    variations = [
        r for r in recipes
        if not getattr(r, "is_master", False) and getattr(r, "test_sequence", None) is None
    ]
    variations.sort(key=lambda r: int(getattr(r, "version_number", 0) or 0), reverse=True)

    variation_tests = [
        r for r in recipes
        if not getattr(r, "is_master", False) and getattr(r, "test_sequence", None) is not None
    ]
    variation_tests_by_parent: Dict[int, List[Recipe]] = {}
    for test in variation_tests:
        parent_id = getattr(test, "parent_recipe_id", None)
        if parent_id:
            variation_tests_by_parent.setdefault(int(parent_id), []).append(test)
    for tests in variation_tests_by_parent.values():
        tests.sort(key=lambda r: int(getattr(r, "test_sequence", 0) or 0))

    variation_map: Dict[str, dict] = {}
    for version in variations:
        variation_name = (
            getattr(version, "variation_name", None)
            or getattr(version, "name", None)
            or "Variation"
        )
        branch = variation_map.setdefault(
            variation_name,
            {"name": variation_name, "versions": []},
        )
        branch["versions"].append(
            {
                "version": version,
                "tests": variation_tests_by_parent.get(version.id, []),
            }
        )
    variation_branches = sorted(variation_map.values(), key=lambda b: b["name"].lower())
    return master_branches, variation_branches
