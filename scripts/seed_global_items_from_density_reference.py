import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, GlobalItem, InventoryCategory


def load_density_json():
	base = os.path.dirname(os.path.dirname(__file__))
	path = os.path.join(base, 'data', 'density_reference.json')
	if not os.path.exists(path):
		return None
	with open(path, 'r') as f:
		return json.load(f)


def seed():
	app = create_app()
	with app.app_context():
		payload = load_density_json()
		if not payload:
			print('No density_reference.json found; skipping seeding')
			return
		count = 0
		for item in payload.get('common_densities', []):
			name = item.get('name')
			if not name:
				continue
			density = item.get('density_g_per_ml')
			reference_category = item.get('category') or None
			aka = item.get('aka') or []
			# Upsert by (name, item_type='ingredient')
			existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
			if existing:
				existing.density = density
				existing.reference_category = reference_category
				existing.aka_names = aka
			else:
				gi = GlobalItem(
					name=name,
					item_type='ingredient',
					default_unit=item.get('default_unit') or None,
					density=density,
					reference_category=reference_category,
					suggested_inventory_category_id=None,
					aka_names=aka,
				)
				db.session.add(gi)
				count += 1
		db.session.commit()
		print(f'Seeded/updated {count} global ingredient items')


if __name__ == '__main__':
	seed()

