"""Lineage utilities for recipe trees.

Synopsis:
Serializes lineage trees and builds navigation paths.

Glossary:
- Lineage tree: Hierarchy of versions, variations, and clones.
- Current node: Version flagged as current for a branch.
"""
from __future__ import annotations

from typing import Dict, List, Optional

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
