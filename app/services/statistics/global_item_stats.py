from datetime import datetime
from sqlalchemy import func, case
from app.models import db, InventoryItem, InventoryLot, UnifiedInventoryHistory


class GlobalItemStatsService:
	@staticmethod
	def get_rollup(global_item_id: int):
		# Aggregate across all orgs for items linked to this global item
		item_ids_subq = db.session.query(InventoryItem.id).filter(InventoryItem.global_item_id == global_item_id).subquery()

		# Average consumer cost (weighted by remaining or original quantity). Use lot unit_cost as proxy
		avg_cost = db.session.query(func.avg(InventoryLot.unit_cost)).join(
			item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id
		).scalar()

		# Average age in inventory (days) based on lots still holding quantity
		age_days = db.session.query(
			func.avg(func.extract('epoch', func.now() - InventoryLot.received_date) / 86400.0)
		).join(item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id).filter(InventoryLot.remaining_quantity > 0).scalar()

		# Average expired amounts (quantity and time to expiry) based on lots that are expired with remaining qty
		expired_qty = db.session.query(func.avg(InventoryLot.remaining_quantity)).join(
			item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id
		).filter(
			InventoryLot.expiration_date.isnot(None),
			InventoryLot.expiration_date < func.now(),
			InventoryLot.remaining_quantity > 0
		).scalar()

		# Average days past expiration for expired lots
		avg_days_past = db.session.query(
			func.avg(func.extract('epoch', func.now() - InventoryLot.expiration_date) / 86400.0)
		).join(item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id).filter(
			InventoryLot.expiration_date.isnot(None),
			InventoryLot.expiration_date < func.now(),
			InventoryLot.remaining_quantity > 0
		).scalar()

		return {
			'average_cost_per_unit': float(avg_cost) if avg_cost is not None else None,
			'average_stock_age_days': float(age_days) if age_days is not None else None,
			'average_expired_quantity': float(expired_qty) if expired_qty is not None else None,
			'average_days_past_expiration': float(avg_days_past) if avg_days_past is not None else None,
		}

