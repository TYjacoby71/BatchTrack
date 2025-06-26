
from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    print("=== INVENTORY_HISTORY TABLE COLUMNS ===")
    columns = inspector.get_columns('inventory_history')
    for col in columns:
        print(f"- {col['name']} ({col['type']})")
    
    print("\n=== INVENTORY_ITEM TABLE COLUMNS ===")  
    columns = inspector.get_columns('inventory_item')
    for col in columns:
        print(f"- {col['name']} ({col['type']})")
