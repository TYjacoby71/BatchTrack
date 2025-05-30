
from app import app, db
from models import Unit
import json

def load_startup_units():
    """Load startup units from export data"""
    with app.app_context():
        # Check if we have the legacy export file
        try:
            with open('units_export_20250502_225442.json', 'r') as f:
                data = json.load(f)
                units = data['units']
        except FileNotFoundError:
            print("No unit export file found - skipping unit startup")
            return

        for unit_data in units:
            if Unit.query.filter_by(name=unit_data['name']).first():
                print(f"[SKIPPED] Unit '{unit_data['name']}' already exists.")
                continue

            # Create unit with only valid fields
            unit = Unit(
                name=unit_data['name'],
                abbreviation=unit_data.get('abbreviation', ''),
                type=unit_data.get('type', 'weight'),
                base_unit=unit_data.get('base_unit', ''),
                multiplier=unit_data.get('multiplier', 1.0)
            )
            db.session.add(unit)
            print(f"[ADDED] Unit '{unit.name}' ({unit.type})")

        db.session.commit()
        print("✅ Startup unit service complete")

if __name__ == '__main__':
    load_startup_units()
