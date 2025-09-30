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

def process_category_files():
	"""Process all category JSON files in the seeders directory"""
	import glob
	base_path = os.path.dirname(os.path.dirname(__file__))
	
	# Process ingredients
	ingredient_files = glob.glob(os.path.join(base_path, 'app/seeders/globallist/ingredients/categories/*.json'))
	container_files = glob.glob(os.path.join(base_path, 'app/seeders/globallist/containers/categories/*.json'))
	packaging_files = glob.glob(os.path.join(base_path, 'app/seeders/globallist/packaging/categories/*.json'))
	consumable_files = glob.glob(os.path.join(base_path, 'app/seeders/globallist/consumables/categories/*.json'))
	
	created_categories = 0
	created_items = 0
	updated_items = 0
	
	# Process ingredient categories
	for file_path in ingredient_files:
		with open(file_path, 'r') as f:
			data = json.load(f)
			
		cat_name = data.get('category_name')
		if not cat_name:
			continue
			
		# Create or get category
		category = IngredientCategory.query.filter_by(name=cat_name, organization_id=None).first()
		if not category:
			category = IngredientCategory(
				name=cat_name,
				description=data.get('description', ''),
				default_density=data.get('default_density'),
				organization_id=None,
				is_global_category=True
			)
			db.session.add(category)
			db.session.flush()
			created_categories += 1
		
		# Process items
		for item_data in data.get('items', []):
			name = item_data.get('name')
			if not name:
				continue
				
			existing = GlobalItem.query.filter_by(name=name, item_type='ingredient').first()
			if existing:
				# Update existing
				for field in ['density_g_per_ml', 'aka_names', 'default_unit', 'saponification_value', 
							 'iodine_value', 'melting_point_c', 'flash_point_c', 'ph_value',
							 'moisture_content_percent', 'shelf_life_months', 'comedogenic_rating']:
					if field == 'density_g_per_ml' and item_data.get(field):
						existing.density = item_data[field]
					elif field == 'aka_names' and item_data.get(field):
						existing.aka_names = item_data[field]
					elif field in item_data and item_data[field] is not None:
						setattr(existing, field, item_data[field])
				existing.ingredient_category_id = category.id
				updated_items += 1
			else:
				# Create new
				gi = GlobalItem(
					name=name,
					item_type='ingredient',
					density=item_data.get('density_g_per_ml'),
					aka_names=item_data.get('aka_names', []),
					default_unit=item_data.get('default_unit'),
					ingredient_category_id=category.id,
					saponification_value=item_data.get('saponification_value'),
					iodine_value=item_data.get('iodine_value'),
					melting_point_c=item_data.get('melting_point_c'),
					flash_point_c=item_data.get('flash_point_c'),
					ph_value=item_data.get('ph_value'),
					moisture_content_percent=item_data.get('moisture_content_percent'),
					shelf_life_months=item_data.get('shelf_life_months'),
					comedogenic_rating=item_data.get('comedogenic_rating')
				)
				db.session.add(gi)
				created_items += 1
	
	# Process container categories
	for file_path in container_files:
		with open(file_path, 'r') as f:
			data = json.load(f)
			
		for item_data in data.get('items', []):
			name = item_data.get('name')
			if not name:
				continue
				
			existing = GlobalItem.query.filter_by(name=name, item_type='container').first()
			if existing:
				# Update existing container
				for field in ['capacity', 'capacity_unit', 'container_material', 'container_type', 
							 'container_style', 'container_color', 'aka_names']:
					if field in item_data and item_data[field] is not None:
						setattr(existing, field, item_data[field])
				updated_items += 1
			else:
				# Create new container
				gi = GlobalItem(
					name=name,
					item_type='container',
					capacity=item_data.get('capacity'),
					capacity_unit=item_data.get('capacity_unit'),
					container_material=data.get('material') or item_data.get('container_material'),
					container_type=item_data.get('container_type'),
					container_style=item_data.get('container_style'),
					container_color=item_data.get('container_color'),
					aka_names=item_data.get('aka_names', [])
				)
				db.session.add(gi)
				created_items += 1
	
	return created_categories, created_items, updated_items

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
					is_active=True,
					# Set visibility flags from JSON
					show_saponification_value=cat_data.get('show_saponification_value', False),
					show_iodine_value=cat_data.get('show_iodine_value', False),
					show_melting_point=cat_data.get('show_melting_point', False),
					show_flash_point=cat_data.get('show_flash_point', False),
					show_ph_value=cat_data.get('show_ph_value', False),
					show_moisture_content=cat_data.get('show_moisture_content', False),
					show_shelf_life_months=cat_data.get('show_shelf_life_months', False),
					show_comedogenic_rating=cat_data.get('show_comedogenic_rating', False)
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
				# Update visibility flags from JSON
				curated_cat.show_saponification_value = cat_data.get('show_saponification_value', False)
				curated_cat.show_iodine_value = cat_data.get('show_iodine_value', False)
				curated_cat.show_melting_point = cat_data.get('show_melting_point', False)
				curated_cat.show_flash_point = cat_data.get('show_flash_point', False)
				curated_cat.show_ph_value = cat_data.get('show_ph_value', False)
				curated_cat.show_moisture_content = cat_data.get('show_moisture_content', False)
				curated_cat.show_shelf_life_months = cat_data.get('show_shelf_life_months', False)
				curated_cat.show_comedogenic_rating = cat_data.get('show_comedogenic_rating', False)

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

		


if __name__ == '__main__':
	seed()