
from app import app, db
from models import Unit
import json

JSON_PATH = 'units_export_20250502_225442.json'

def load_legacy_units():
    with app.app_context():
        with open(JSON_PATH, 'r') as f:
            data = json.load(f)
            units = data['units']  # Access the 'units' key from the JSON

        for unit_data in units:
            if Unit.query.filter_by(name=unit_data['name']).first():
                print(f"[SKIPPED] Unit '{unit_data['name']}' already exists.")
                continue

            unit = Unit(**unit_data)
            db.session.add(unit)
            print(f"[ADDED] Unit '{unit.name}' ({unit.type})")

        db.session.commit()
        print("✅ Legacy units import complete.")

if __name__ == '__main__':
    load_legacy_units()
