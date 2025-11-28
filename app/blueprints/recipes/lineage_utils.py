from __future__ import annotations

from typing import Dict, List, Optional

from app.models import Recipe


def serialize_lineage_tree(node_recipe: Recipe, nodes: Dict[int, dict], current_id: int) -> dict:
    node_payload = {
        'id': node_recipe.id,
        'name': node_recipe.name,
        'organization_name': node_recipe.organization.name if node_recipe.organization else None,
        'organization_id': node_recipe.organization_id,
        'origin_type': node_recipe.org_origin_type,
        'origin_purchased': node_recipe.org_origin_purchased,
        'is_current': node_recipe.id == current_id,
        'status': node_recipe.status,
        'children': [],
    }

    for child in nodes.get(node_recipe.id, {}).get('children', []):
        child_recipe = nodes[child['id']]['recipe']
        node_payload['children'].append(
            {
                'edge_type': child['edge'],
                'node': serialize_lineage_tree(child_recipe, nodes, current_id),
            }
        )

    return node_payload


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
