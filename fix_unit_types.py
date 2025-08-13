
#!/usr/bin/env python3
"""
Fix corrupted unit types in the database
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app
from app.models import db, Unit

def fix_unit_types():
    """Fix the unit types that got corrupted"""
    
    # Define the correct unit types for each unit
    correct_types = {
        # Weight units
        'gram': 'weight', 'kg': 'weight', 'mg': 'weight', 'oz': 'weight', 
        'lb': 'weight', 'ton': 'weight',
        
        # Volume units  
        'ml': 'volume', 'liter': 'volume', 'tsp': 'volume', 'tbsp': 'volume',
        'cup': 'volume', 'pint': 'volume', 'quart': 'volume', 'gallon': 'volume',
        'floz': 'volume', 'drop': 'volume', 'dram': 'volume', 'cubicinch': 'volume',
        'cubicfoot': 'volume', 'cubicyard': 'volume',
        
        # Length units
        'cm': 'length', 'mm': 'length', 'inch': 'length', 'ft': 'length',
        'yard': 'length', 'meter': 'length',
        
        # Area units
        'sqcm': 'area', 'sqm': 'area', 'sqinch': 'area', 'sqft': 'area',
        'sqyard': 'area', 'acre': 'area',
        
        # Count units
        'count': 'count', 'pack': 'count', 'dozen': 'count', 'unit': 'count',
        'batch': 'count', 'pair': 'count',
        
        # Time units
        'second': 'time', 'minute': 'time', 'hour': 'time', 'day': 'time',
        'week': 'time', 'month': 'time', 'year': 'time'
    }
    
    print("🔧 Fixing corrupted unit types...")
    
    fixed_count = 0
    for unit_name, correct_type in correct_types.items():
        unit = Unit.query.filter_by(name=unit_name).first()
        if unit and unit.unit_type != correct_type:
            print(f"   ✅ Fixing {unit_name}: {unit.unit_type} → {correct_type}")
            unit.unit_type = correct_type
            fixed_count += 1
    
    if fixed_count > 0:
        db.session.commit()
        print(f"✅ Fixed {fixed_count} unit types")
    else:
        print("ℹ️  No unit types needed fixing")
    
    # Verify the fix
    print("\n📊 Unit type summary:")
    from sqlalchemy import func
    type_counts = db.session.query(
        Unit.unit_type, 
        func.count(Unit.id).label('count')
    ).group_by(Unit.unit_type).all()
    
    for unit_type, count in type_counts:
        print(f"   {unit_type}: {count} units")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        fix_unit_types()
