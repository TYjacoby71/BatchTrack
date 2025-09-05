import json
import os
import sys

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, GlobalItem, IngredientCategory


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

		created_categories = 0
		created_items = 0
		updated_items = 0

		# New structure: { "categories": [ { name, default_density, items: [ { name, density_g_per_ml, aka, default_unit } ] } ] }
		if 'categories' in payload:
			for cat in payload['categories']:
				cat_name = (cat.get('name') or '').strip()
				if not cat_name:
					continue
				default_density = cat.get('default_density')
				curated_cat = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
				if not curated_cat:
					curated_cat = IngredientCategory(name=cat_name, default_density=default_density, organization_id=None, is_active=True)
					db.session.add(curated_cat)
					db.session.flush()
					created_categories += 1
				else:
					if default_density is not None:
						curated_cat.default_density = default_density

				for it in cat.get('items', []):
					name = (it.get('name') or '').strip()
					if not name:
						continue
					density = it.get('density_g_per_ml')
					aka = it.get('aka') or []
					default_unit = it.get('default_unit') or None
					existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
					if existing:
						existing.density = density
						existing.aka_names = aka
						existing.default_unit = default_unit
						existing.ingredient_category_id = curated_cat.id
						updated_items += 1
					else:
						gi = GlobalItem(
							name=name,
							item_type='ingredient',
							default_unit=default_unit,
							density=density,
							ingredient_category_id=curated_cat.id,
							suggested_inventory_category_id=None,
							aka_names=aka,
						)
						db.session.add(gi)
						created_items += 1

			db.session.commit()
			print(f'Categories created: {created_categories}; Items created: {created_items}; Items updated: {updated_items}')
			return

		# Legacy structure fallback
		count = 0
		for item in payload.get('common_densities', []):
			name = item.get('name')
			if not name:
				continue
			density = item.get('density_g_per_ml')
			reference_category = item.get('category') or None
			aka = item.get('aka') or []
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
		print(f'(Legacy) Seeded/updated {count} global ingredient items')


if __name__ == '__main__':
	seed()

