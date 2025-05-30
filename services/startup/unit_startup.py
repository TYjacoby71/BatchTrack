
import json
from app import app, db
from models import Unit

JSON_PATH = 'units_export_20250502_225442.json'

def startup_unit_service():
    """Import legacy units using proper creation workflows"""
    with app.app_context():
        try:
            with open(JSON_PATH, 'r') as f:
                data = json.load(f)
                units_data = data.get('units', [])
        except FileNotFoundError:
            print(f"❌ Units file {JSON_PATH} not found")
            return False

        created_count = 0
        skipped_count = 0
        
        print("🚀 Starting unit import service...")

        for unit_data in units_data:
            # Check if unit already exists
            existing_unit = Unit.query.filter_by(name=unit_data['name']).first()
            if existing_unit:
                print(f"[SKIPPED] Unit '{unit_data['name']}' already exists")
                skipped_count += 1
                continue

            # Create new unit with validation
            try:
                unit = Unit(
                    name=unit_data['name'],
                    type=unit_data['type'],
                    base_unit=unit_data['base_unit'],
                    multiplier_to_base=unit_data['multiplier_to_base'],
                    user_id=unit_data.get('user_id'),
                    is_custom=unit_data.get('is_custom', False),
                    is_mapped=unit_data.get('is_mapped', False)
                )
                
                db.session.add(unit)
                print(f"[ADDED] Unit '{unit.name}' ({unit.type}) - {unit.multiplier_to_base}x {unit.base_unit}")
                created_count += 1
                
            except Exception as e:
                print(f"[ERROR] Failed to create unit '{unit_data['name']}': {str(e)}")
                db.session.rollback()
                continue

        db.session.commit()
        print(f"✅ Unit startup complete: {created_count} units created, {skipped_count} skipped")
        return True

if __name__ == '__main__':
    startup_unit_service()
