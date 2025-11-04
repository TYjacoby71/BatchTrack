
import os, sys, json, csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from app.models import db, GlobalItem


def _normalize_header(name: str) -> str:
	return (name or '').strip().lower()


def _to_list(val):
	if val is None:
		return None
	if isinstance(val, list):
		return [str(x).strip() for x in val if str(x).strip()]
	# support semicolon or comma separation
	parts = [p.strip() for p in str(val).replace(';', ',').split(',')]
	return [p for p in parts if p]


def _iter_json(path: str):
	with open(path, 'r') as f:
		payload = json.load(f)
		items = payload.get('items') if isinstance(payload, dict) else payload
		if not isinstance(items, list):
			raise ValueError('JSON must be a list or an object with an "items" list')
		for row in items:
			yield {
				'name': row.get('name'),
				'capacity': row.get('capacity'),
				'capacity_unit': row.get('capacity_unit'),
				'container_material': row.get('container_material'),
				'container_type': row.get('container_type'),
				'container_style': row.get('container_style'),
				'container_color': row.get('container_color'),
				'aka_names': row.get('aka_names'),
			}


def _iter_csv(path: str):
	with open(path, newline='') as f:
		reader = csv.DictReader(f)
		headers = {h: _normalize_header(h) for h in reader.fieldnames or []}
		for row in reader:
			def get(key):
				for k, norm in headers.items():
					if norm == key:
						return row.get(k)
				return None
			yield {
				'name': get('name'),
				'capacity': get('capacity'),
				'capacity_unit': get('capacity_unit'),
				'container_material': get('container_material'),
				'container_type': get('container_type'),
				'container_style': get('container_style'),
				'container_color': get('container_color'),
				'aka_names': get('aka_names'),
			}


def _parse_float(val):
	if val in (None, ''):
		return None
	try:
		return float(val)
	except Exception:
		return None


def upsert_containers(input_path: str):
	app = create_app()
	with app.app_context():
		created = 0
		updated = 0
		if input_path.lower().endswith('.json'):
			rows = _iter_json(input_path)
		elif input_path.lower().endswith('.csv'):
			rows = _iter_csv(input_path)
		else:
			raise ValueError('Unsupported file type. Use .json or .csv')

		for row in rows:
			name = (row.get('name') or '').strip()
			if not name:
				continue
			capacity = _parse_float(row.get('capacity'))
			cap_unit = (row.get('capacity_unit') or '').strip() or None
			material = (row.get('container_material') or '').strip() or None
			ctype = (row.get('container_type') or '').strip() or None
			style = (row.get('container_style') or '').strip() or None
			color = (row.get('container_color') or '').strip() or None
			aka_names = _to_list(row.get('aka_names'))

			# Uniqueness signature for curated container
			existing = GlobalItem.query.filter_by(
				name=name, item_type='container', capacity=capacity, capacity_unit=cap_unit,
				container_material=material, container_type=ctype, container_style=style, container_color=color
			).first()

			if existing:
				# Update synonyms if provided
				if aka_names:
					existing.aka_names = aka_names
				updated += 1
			else:
				gi = GlobalItem(
					name=name,
					item_type='container',
					capacity=capacity,
					capacity_unit=cap_unit,
					container_material=material,
					container_type=ctype,
					container_style=style,
					container_color=color,
					aka_names=aka_names
				)
				db.session.add(gi)
				created += 1

		db.session.commit()
		print(f'Containers created: {created}; updated: {updated}')


def generate_container_attribute_files():
	"""Generate JSON files for container attributes based on existing database data"""
	app = create_app()
	with app.app_context():
		print("=== Generating Container Attribute Files ===")
		
		# Query distinct values
		materials_query = db.session.query(GlobalItem.container_material)\
			.filter(GlobalItem.container_material.isnot(None), GlobalItem.item_type == 'container')\
			.distinct().all()
		materials = sorted([m[0] for m in materials_query if m[0]])
		
		types_query = db.session.query(GlobalItem.container_type)\
			.filter(GlobalItem.container_type.isnot(None), GlobalItem.item_type == 'container')\
			.distinct().all()
		types = sorted([t[0] for t in types_query if t[0]])
		
		styles_query = db.session.query(GlobalItem.container_style)\
			.filter(GlobalItem.container_style.isnot(None), GlobalItem.item_type == 'container')\
			.distinct().all()
		styles = sorted([s[0] for s in styles_query if s[0]])
		
		colors_query = db.session.query(GlobalItem.container_color)\
			.filter(GlobalItem.container_color.isnot(None), GlobalItem.item_type == 'container')\
			.distinct().all()
		colors = sorted([c[0] for c in colors_query if c[0]])
		
		# Create directory
		attributes_dir = os.path.join(os.path.dirname(__file__), 'globallist', 'containers', 'attributes')
		os.makedirs(attributes_dir, exist_ok=True)
		
		# Create JSON files
		files_created = []
		
		if materials:
			materials_file = os.path.join(attributes_dir, 'materials.json')
			with open(materials_file, 'w') as f:
				json.dump({"materials": materials}, f, indent=2)
			files_created.append('materials.json')
			print(f"  ✅ Created materials.json with {len(materials)} materials")
		
		if types:
			types_file = os.path.join(attributes_dir, 'types.json')
			with open(types_file, 'w') as f:
				json.dump({"types": types}, f, indent=2)
			files_created.append('types.json')
			print(f"  ✅ Created types.json with {len(types)} types")
		
		if styles:
			styles_file = os.path.join(attributes_dir, 'styles.json')
			with open(styles_file, 'w') as f:
				json.dump({"styles": styles}, f, indent=2)
			files_created.append('styles.json')
			print(f"  ✅ Created styles.json with {len(styles)} styles")
		
		if colors:
			colors_file = os.path.join(attributes_dir, 'colors.json')
			with open(colors_file, 'w') as f:
				json.dump({"colors": colors}, f, indent=2)
			files_created.append('colors.json')
			print(f"  ✅ Created colors.json with {len(colors)} colors")
		
		print(f"\n📁 Container attribute files created in: {attributes_dir}")
		return files_created


if __name__ == '__main__':
	if len(sys.argv) < 2:
		print('Usage:')
		print('  python app/seeders/seed_containers.py <path-to-json-or-csv>  # Seed containers from file')
		print('  python app/seeders/seed_containers.py --generate-attributes    # Generate attribute files from DB')
		sys.exit(1)
	
	if sys.argv[1] == '--generate-attributes':
		generate_container_attribute_files()
	else:
		upsert_containers(sys.argv[1])
