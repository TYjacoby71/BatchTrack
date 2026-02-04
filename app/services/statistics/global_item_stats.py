from datetime import datetime

from sqlalchemy import func

from app.models import db, InventoryItem, InventoryLot, RecipeIngredient


class GlobalItemStatsService:
	@staticmethod
	def get_rollup(global_item_id: int):
		# Aggregate across all orgs for items linked to this global item
		item_ids_subq = db.session.query(InventoryItem.id).filter(InventoryItem.global_item_id == global_item_id).subquery()

		# Adoption counts
		organizations = db.session.query(func.count(func.distinct(InventoryItem.organization_id))).filter(
			InventoryItem.global_item_id == global_item_id,
			InventoryItem.organization_id.isnot(None),
		).scalar()

		recipes = db.session.query(func.count(func.distinct(RecipeIngredient.recipe_id))).join(
			InventoryItem, RecipeIngredient.inventory_item_id == InventoryItem.id
		).filter(
			InventoryItem.global_item_id == global_item_id,
			RecipeIngredient.recipe_id.isnot(None),
		).scalar()

		# Average consumer cost (weighted by remaining or original quantity). Use lot unit_cost as proxy
		avg_cost = db.session.query(func.avg(InventoryLot.unit_cost)).join(
			item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id
		).scalar()

		# Average age in inventory (days) based on lots still holding quantity
		age_days = db.session.query(
			func.avg(func.extract('epoch', func.now() - InventoryLot.received_date) / 86400.0)
		).join(item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id).filter(InventoryLot.remaining_quantity_base > 0).scalar()

		# Average expired amounts (quantity and time to expiry) based on lots that are expired with remaining qty
		expired_qty = db.session.query(func.avg(InventoryLot.remaining_quantity)).join(
			item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id
		).filter(
			InventoryLot.expiration_date.isnot(None),
			InventoryLot.expiration_date < func.now(),
			InventoryLot.remaining_quantity_base > 0
		).scalar()

		# Average days past expiration for expired lots
		avg_days_past = db.session.query(
			func.avg(func.extract('epoch', func.now() - InventoryLot.expiration_date) / 86400.0)
		).join(item_ids_subq, InventoryLot.inventory_item_id == item_ids_subq.c.id).filter(
			InventoryLot.expiration_date.isnot(None),
			InventoryLot.expiration_date < func.now(),
			InventoryLot.remaining_quantity_base > 0
		).scalar()

		return {
			'organizations': int(organizations or 0),
			'recipes': int(recipes or 0),
			'average_cost_per_unit': float(avg_cost) if avg_cost is not None else None,
			'average_stock_age_days': float(age_days) if age_days is not None else None,
			'average_expired_quantity': float(expired_qty) if expired_qty is not None else None,
			'average_days_past_expiration': float(avg_days_past) if avg_days_past is not None else None,
		}

	@staticmethod
	def get_cost_distribution(global_item_id: int) -> dict:
		"""Compute cost distribution across all orgs for a global item using InventoryLot.unit_cost.
		Rules:
		- Include only lots where unit_cost > 0
		- Derive non-outlier stats via IQR (exclude values < Q1 - 1.5*IQR or > Q3 + 1.5*IQR)
		- Return mean (trimmed), low/high (non-outlier bounds), min/max, counts and a simple histogram
		"""
		# Collect costs
		cost_rows = db.session.query(InventoryLot.unit_cost).join(
			InventoryItem, InventoryLot.inventory_item_id == InventoryItem.id
		).filter(
			InventoryItem.global_item_id == global_item_id,
			InventoryLot.unit_cost.isnot(None),
			InventoryLot.unit_cost > 0
		).all()

		costs = [float(r[0]) for r in cost_rows if r and r[0] is not None]
		if not costs:
			return {
				'count': 0,
				'mean_ex_outliers': None,
				'low': None,
				'high': None,
				'min': None,
				'max': None,
				'outliers_low_count': 0,
				'outliers_high_count': 0,
				'histogram': []
			}

		costs.sort()

		def percentile(sorted_vals, p):
			if not sorted_vals:
				return None
			n = len(sorted_vals)
			k = (n - 1) * p
			f = int(k)
			c = min(f + 1, n - 1)
			if f == c:
				return sorted_vals[int(k)]
			return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

		q1 = percentile(costs, 0.25)
		q3 = percentile(costs, 0.75)
		iqr = (q3 - q1) if (q1 is not None and q3 is not None) else 0
		lower_fence = q1 - 1.5 * iqr if q1 is not None else None
		upper_fence = q3 + 1.5 * iqr if q3 is not None else None

		non_outliers = [v for v in costs if (lower_fence is None or v >= lower_fence) and (upper_fence is None or v <= upper_fence)]
		outliers_low = [v for v in costs if lower_fence is not None and v < lower_fence]
		outliers_high = [v for v in costs if upper_fence is not None and v > upper_fence]

		trimmed_mean = sum(non_outliers) / len(non_outliers) if non_outliers else None
		low = min(non_outliers) if non_outliers else None
		high = max(non_outliers) if non_outliers else None
		min_v = min(costs)
		max_v = max(costs)

		# Build a simple histogram with 10 bins across non-outlier range (fallback to full range if needed)
		hist = []
		if non_outliers and (high is not None) and (low is not None) and high > low:
			bins = 10
			width = (high - low) / bins
			for i in range(bins):
				start = low + i * width
				end = start + width if i < bins - 1 else high
				count = len([v for v in non_outliers if (v >= start and (v < end or (i == bins - 1 and v <= end)))])
				hist.append({'bin_start': start, 'bin_end': end, 'count': count})

		return {
			'count': len(costs),
			'mean_ex_outliers': trimmed_mean,
			'low': low,
			'high': high,
			'min': min_v,
			'max': max_v,
			'outliers_low_count': len(outliers_low),
			'outliers_high_count': len(outliers_high),
			'histogram': hist
		}

