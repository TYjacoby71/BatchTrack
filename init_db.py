
from app import app, db  # Must import from app.py where db is bound to app
from models import User, Unit, IngredientCategory
from werkzeug.security import generate_password_hash

def seed_units():
    units = [
        {"name": "gram", "type": "weight", "base_unit": "gram", "multiplier_to_base": 1.0},
        {"name": "ml", "type": "volume", "base_unit": "ml", "multiplier_to_base": 1.0},
        {"name": "count", "type": "count", "base_unit": "count", "multiplier_to_base": 1.0},
        {"name": "tsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 4.92892},
        {"name": "tbsp", "type": "volume", "base_unit": "ml", "multiplier_to_base": 14.7868},
    ]
    for unit in units:
        if not Unit.query.filter_by(name=unit["name"]).first():
            db.session.add(Unit(**unit))

def seed_categories():
    categories = [
        {"name": "Oil", "default_density": 0.92},
        {"name": "Liquid", "default_density": 1.0},
        {"name": "Solid", "default_density": 0.8},
        {"name": "Powder", "default_density": 0.5},
    ]
    for cat in categories:
        if not IngredientCategory.query.filter_by(name=cat["name"]).first():
            db.session.add(IngredientCategory(**cat))

def init_db():
    with app.app_context():
        db.create_all()
        seed_units()
        seed_categories()
        
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)
            
        db.session.commit()
        print("Database initialized and seeded.")

if __name__ == "__main__":
    init_db()
