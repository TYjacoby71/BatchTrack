
import json
import os
import sys
import glob

# Add the parent directory to the Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, GlobalItem, IngredientCategory


def load_category_files():
	"""Load category files from app/seeders/globallist/*/categories/"""
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


def seed_global_inventory_library():
	"""Seed all global inventory types from JSON category files"""
	app = create_app()
	with app.app_context():
		print("=== Seeding Global Inventory Library ===")
		print("Processing all inventory types: ingredients, containers, packaging, consumables")
		
		created_categories = 0
		created_items = 0
		updated_items = 0

		# Load categories from individual JSON files
		categories = load_category_files()
		print(f"Found {len(categories)} category files to process")

		for cat_data in categories:
			cat_name = cat_data.get('category_name', '').strip()
			if not cat_name:
				print(f"  ⚠️  Skipping category with no name in {cat_data}")
				continue

			item_type = cat_data.get('item_type', 'ingredient')
			default_density = cat_data.get('default_density')
			description = cat_data.get('description', '')

			print(f"\n📁 Processing {item_type} category: {cat_name}")

			# Create or update ingredient category (only for ingredients)
			curated_cat = None
			if item_type == 'ingredient':
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
					print(f"    ✅ Created ingredient category: {cat_name}")
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
					print(f"    ↻ Updated ingredient category: {cat_name}")

			# Process items in the category
			items_processed = 0
			for item_data in cat_data.get('items', []):
				name = item_data.get('name', '').strip()
				if not name:
					continue

				# Common fields for all item types
				density = item_data.get('density_g_per_ml')
				aka = item_data.get('aka_names', item_data.get('aka', []))
				default_unit = item_data.get('default_unit')
				perishable = item_data.get('perishable', False)
				shelf_life_days = item_data.get('shelf_life_days')
				
				# Container/packaging specific fields
				capacity = item_data.get('capacity')
				capacity_unit = item_data.get('capacity_unit')
				container_material = cat_data.get('material') or item_data.get('container_material')
				container_type = item_data.get('container_type')
				container_style = item_data.get('container_style')
				container_color = item_data.get('container_color')

				# Ingredient-specific soap making fields
				sap_value = item_data.get('saponification_value')
				iodine_val = item_data.get('iodine_value')
				melting_pt = item_data.get('melting_point_c')
				flash_pt = item_data.get('flash_point_c')
				ph_val = item_data.get('ph_value')
				moisture = item_data.get('moisture_content_percent')
				shelf_life_months = item_data.get('shelf_life_months')
				comedogenic = item_data.get('comedogenic_rating')

				# Create or update global item
				existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
				if existing:
					# Update existing item
					existing.density = density
					existing.aka_names = aka
					existing.default_unit = default_unit
					existing.ingredient_category_id = curated_cat.id if (item_type == 'ingredient' and curated_cat) else None
					existing.default_is_perishable = perishable
					existing.recommended_shelf_life_days = shelf_life_days
					existing.capacity = capacity
					existing.capacity_unit = capacity_unit
					existing.container_material = container_material
					existing.container_type = container_type
					existing.container_style = container_style
					existing.container_color = container_color
					
					# Update soap making fields for ingredients
					if item_type == 'ingredient':
						existing.saponification_value = sap_value
						existing.iodine_value = iodine_val
						existing.melting_point_c = melting_pt
						existing.flash_point_c = flash_pt
						existing.ph_value = ph_val
						existing.moisture_content_percent = moisture
						existing.shelf_life_months = shelf_life_months
						existing.comedogenic_rating = comedogenic
					
					updated_items += 1
				else:
					# Create new item
					gi = GlobalItem(
						name=name,
						item_type=item_type,
						default_unit=default_unit,
						density=density,
						ingredient_category_id=curated_cat.id if (item_type == 'ingredient' and curated_cat) else None,
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
					
					# Add soap making fields for ingredients
					if item_type == 'ingredient':
						gi.saponification_value = sap_value
						gi.iodine_value = iodine_val
						gi.melting_point_c = melting_pt
						gi.flash_point_c = flash_pt
						gi.ph_value = ph_val
						gi.moisture_content_percent = moisture
						gi.shelf_life_months = shelf_life_months
						gi.comedogenic_rating = comedogenic
					
					db.session.add(gi)
					created_items += 1
				
				items_processed += 1

			if items_processed > 0:
				print(f"    📦 Processed {items_processed} items")

		db.session.commit()
		
		print(f"\n🎉 Global Inventory Library Seeding Complete!")
		print(f"📊 Summary:")
		print(f"   Categories created: {created_categories}")
		print(f"   Items created: {created_items}")
		print(f"   Items updated: {updated_items}")
		print(f"   Total items: {created_items + updated_items}")


if __name__ == '__main__':
	seed_global_inventory_library()
