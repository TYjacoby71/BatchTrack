
from app import app, db
from models import User, Unit, IngredientCategory
from werkzeug.security import generate_password_hash

from seeders.unit_seeder import seed_units

def seed_categories():
    categories = [
        # Core Categories
        {"name": "Liquid", "default_density": 1.0},
        {"name": "Oil", "default_density": 0.92},
        {"name": "Solid", "default_density": 0.8},
        {"name": "Powder", "default_density": 0.5},
        {"name": "Dairy", "default_density": 1.03},
        {"name": "Syrup", "default_density": 1.33},

        # Specialty Categories
        {"name": "Alcohol", "default_density": 0.789},
        {"name": "Fragrance", "default_density": 0.86},
        {"name": "Gel", "default_density": 1.05},
        {"name": "Wax", "default_density": 0.9},
        {"name": "Extract", "default_density": 1.1},
        {"name": "Clay", "default_density": 1.6},
        {"name": "Other", "default_density": 1.0},
    ]

    for cat in categories:
        if not IngredientCategory.query.filter_by(name=cat["name"]).first():
            db.session.add(IngredientCategory(**cat))

def init_db():
    with app.app_context():
        db.create_all()
        seed_units()
        seed_categories()

        # Default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)

        db.session.commit()
        print("✅ Database initialized with units, categories, and admin user.")

if __name__ == "__main__":
    init_db()
