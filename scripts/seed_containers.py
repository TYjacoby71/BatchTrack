import os, sys, json, csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


if __name__ == '__main__':
	if len(sys.argv) < 2:
		print('Usage: python scripts/seed_containers.py <path-to-json-or-csv>')
		sys.exit(1)
	upsert_containers(sys.argv[1])