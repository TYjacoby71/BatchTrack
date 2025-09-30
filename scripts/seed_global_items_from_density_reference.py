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


def load_category_files():
	"""Load category files from app/seeders/globallist/*/categories/"""
	import os
	import json

	base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'seeders', 'globallist')
	categories = []

	# Load from ingredients, containers, packaging, and consumables
	for item_type in ['ingredients', 'containers', 'packaging', 'consumables']:
		category_path = os.path.join(base_dir, item_type, 'categories')
		
		if not os.path.exists(category_path):
			print(f"Category path not found: {category_path}")
			continue

		for filename in os.listdir(category_path):
			if filename.endswith('.json'):
				filepath = os.path.join(category_path, filename)
				try:
					with open(filepath, 'r') as f:
						category_data = json.load(f)
						# Add item_type to distinguish between categories
						category_data['item_type'] = item_type.rstrip('s')  # Remove plural 's'
						categories.append(category_data)
				except Exception as e:
					print(f"Error loading {filename}: {e}")

	return categories

def seed():
	app = create_app()
	with app.app_context():
		created_categories = 0
		created_items = 0
		updated_items = 0

		# Load categories from individual JSON files
		categories = load_category_files()

		for cat_data in categories:
			cat_name = cat_data.get('category_name', '').strip()
			if not cat_name:
				continue

			default_density = cat_data.get('default_density')
			description = cat_data.get('description', '')

			# Create or update category
			curated_cat = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
			if not curated_cat:
				curated_cat = IngredientCategory(
					name=cat_name,
					description=description,
					default_density=default_density,
					is_global_category=True,
					organization_id=None,
					is_active=True
				)
				db.session.add(curated_cat)
				db.session.flush()
				created_categories += 1
			else:
				# Update existing category
				if default_density is not None:
					curated_cat.default_density = default_density
				if description:
					curated_cat.description = description
				# Ensure global category flag is set
				curated_cat.is_global_category = True

			# Process items in the category
			item_type = cat_data.get('item_type', 'ingredient')
			
			for item_data in cat_data.get('items', []):
				name = item_data.get('name', '').strip()
				if not name:
					continue

				density = item_data.get('density_g_per_ml')
				aka = item_data.get('aka_names', item_data.get('aka', []))
				default_unit = item_data.get('default_unit')
				perishable = item_data.get('perishable', False)
				shelf_life_days = item_data.get('shelf_life_days')
				
				# Container/packaging specific fields
				capacity = item_data.get('capacity')
				capacity_unit = item_data.get('capacity_unit')
				container_material = cat_data.get('material')
				container_type = item_data.get('container_type')
				container_style = item_data.get('container_style')
				container_color = item_data.get('container_color')

				# Create or update global item
				existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
				if existing:
					existing.density = density
					existing.aka_names = aka
					existing.default_unit = default_unit
					existing.ingredient_category_id = curated_cat.id if item_type == 'ingredient' else None
					existing.default_is_perishable = perishable
					existing.recommended_shelf_life_days = shelf_life_days
					existing.capacity = capacity
					existing.capacity_unit = capacity_unit
					existing.container_material = container_material
					existing.container_type = container_type
					existing.container_style = container_style
					existing.container_color = container_color
					updated_items += 1
				else:
					gi = GlobalItem(
						name=name,
						item_type=item_type,
						default_unit=default_unit,
						density=density,
						ingredient_category_id=curated_cat.id if item_type == 'ingredient' else None,
						aka_names=aka,
						default_is_perishable=perishable,
						recommended_shelf_life_days=shelf_life_days,
						capacity=capacity,
						capacity_unit=capacity_unit,
						container_material=container_material,
						container_type=container_type,
						container_style=container_style,
						container_color=container_color,
					)
					db.session.add(gi)
					created_items += 1

		db.session.commit()
		print(f'Categories created: {created_categories}; Items created: {created_items}; Items updated: {updated_items}')

		# Also process legacy density_reference.json if it exists
		payload = load_density_json()
		if payload and 'common_densities' in payload:

		# Use existing list; ensure curated categories exist and attach FK to all items
		created_categories = 0
		created_items = 0
		updated_items = 0

		default_map = {
			'Liquids': 1.0,
			'Dairy': 1.02,
			'Oils': 0.92,
			'Fats': 0.91,
			'Syrups': 1.4,
			'Flours': 0.6,
			'Starches': 0.63,
			'Sugars': 0.85,
			'Sweeteners': 0.67,
			'Salts': 2.16,
			'Leavening': 1.56,
			'Chocolate': 0.71,
			'Spices': 0.57,
			'Herbs': 0.32,
			'Extracts': 0.86,
			'Acids': 1.03,
			'Grains': 0.72,
			'Nuts': 0.55,
			'Seeds': 0.61,
			'Dried Fruits': 0.69,
			'Waxes': 0.93,
			'Clays': 2.45,
			'Essential Oils': 0.89,
			'Cosmetic Ingredients': 1.08,
			'Alcohols': 0.85,
		}

		items = payload.get('common_densities', [])
		# Create curated categories
		for it in items:
			cat_name = (it.get('category') or '').strip()
			if not cat_name:
				continue
			cur = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
			if not cur:
				# Create category without default density - let JSON files handle that
				cur = IngredientCategory(
					name=cat_name, 
					organization_id=None, 
					is_active=True,
					is_global_category=True
				)
				db.session.add(cur)
				db.session.flush()
				created_categories += 1
			elif cur.default_density is None and default_map.get(cat_name) is not None:
				cur.default_density = default_map.get(cat_name)

		# Upsert global items and attach FK
		for it in items:
			name = (it.get('name') or '').strip()
			if not name:
				continue
			density = it.get('density_g_per_ml')
			aka = it.get('aka') or it.get('aliases') or []
			default_unit = it.get('default_unit') or None
			cat_name = (it.get('category') or '').strip()
			cur = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first() if cat_name else None

			existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
			if existing:
				existing.density = density
				existing.aka_names = aka
				existing.default_unit = default_unit
				existing.ingredient_category_id = cur.id if cur else None
				updated_items += 1
			else:
				gi = GlobalItem(
					name=name,
					item_type='ingredient',
					default_unit=default_unit,
					density=density,
					ingredient_category_id=(cur.id if cur else None),
					suggested_inventory_category_id=None,
					aka_names=aka,
				)
				db.session.add(gi)
				created_items += 1

		db.session.commit()
		print(f'Curated categories created: {created_categories}; Items created: {created_items}; Items updated: {updated_items}')


if __name__ == '__main__':
	seed()