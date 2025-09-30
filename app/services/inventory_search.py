from typing import List, Dict, Optional
from flask_login import current_user
from app.models import InventoryItem


class InventorySearchService:
	@staticmethod
	def search_inventory_items(query_text: str, inventory_type: Optional[str], organization_id: int, limit: int = 20) -> List[Dict]:
		"""Org-scoped inventory search returning lightweight dicts for suggestions.

		- query_text: substring match against name (case-insensitive), must be len>=2
		- inventory_type: optional filter ('ingredient','container','packaging','consumable')
		- organization_id: required scoping id
		"""
		if not query_text or len(query_text.strip()) < 2:
			return []

		q = InventoryItem.query.filter(
			InventoryItem.organization_id == organization_id,
			InventoryItem.name.ilike(f"%{query_text.strip()}%")
		)
		if inventory_type:
			q = q.filter(InventoryItem.type == inventory_type)

		items = q.order_by(InventoryItem.name.asc()).limit(limit).all()

		results: List[Dict] = []
		for it in items:
			base = {
				'id': it.id,
				'text': it.name,
				'type': it.type,
			}
			if it.type == 'container':
				base.update({
					'capacity': getattr(it, 'capacity', None),
					'capacity_unit': getattr(it, 'capacity_unit', None),
					'container_material': getattr(it, 'container_material', None),
					'container_type': getattr(it, 'container_type', None),
					'container_style': getattr(it, 'container_style', None),
					'container_color': getattr(it, 'container_color', None),
				})
			results.append(base)

		return results

