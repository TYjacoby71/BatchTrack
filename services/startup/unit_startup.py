from app import app, db
from models import Unit
import json

def load_startup_units():
    """Load startup units from export file"""
    with app.app_context():
        try:
            with open('units_export_20250502_225442.json', 'r') as f:
                data = json.load(f)
                units_data = data.get('units', [])
        except FileNotFoundError:
            print("No units export file found - skipping unit startup")
            return

        print("Loading startup units...")

        for unit_data in units_data:
            # Check if unit already exists
            existing = Unit.query.filter_by(name=unit_data['name']).first()
            if existing:
                print(f"[SKIPPED] Unit '{unit_data['name']}' already exists.")
                continue

            # Create unit with explicit field mapping
            unit = Unit(
                name=unit_data.get('name', ''),
                type=unit_data.get('type', 'weight'),
                base_unit=unit_data.get('base_unit', ''),
                multiplier_to_base=float(unit_data.get('multiplier_to_base', 1.0)),
                is_custom=bool(unit_data.get('is_custom', False)),
                is_mapped=bool(unit_data.get('is_mapped', False))
            )

            db.session.add(unit)
            print(f"[ADDED] Unit '{unit.name}' ({unit.type})")

        db.session.commit()
        print("✅ Startup units service complete")

if __name__ == '__main__':
    load_startup_units()