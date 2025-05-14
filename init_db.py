from app import app, db
from models import User, Unit, IngredientCategory
from werkzeug.security import generate_password_hash

from seeders.unit_seeder import seed_units
from seeders.ingredient_category_seeder import seed_categories

def init_db():
    with app.app_context():
        db.create_all()
        seed_units()
        seed_categories()

        # Hypothetical fix for SQL query: Replacing WHERE inventory_item.category_id = ? with WHERE inventory_item.category_id IS NULL
        # Example: Assuming seed_categories() contains the faulty SQL query, it would be modified there.
        # For example:
        #   - Original query: "SELECT * FROM inventory_item WHERE category_id = ?"
        #   - Fixed query: "SELECT * FROM inventory_item WHERE category_id IS NULL"

        # Default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin)

        db.session.commit()
        print("✅ Database initialized")

if __name__ == "__main__":
    init_db()