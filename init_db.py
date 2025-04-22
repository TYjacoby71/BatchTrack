from app import app, db  # Must import from app.py where db is bound to app
from seeders.unit_seeder import seed_units
from seeders.ingredient_category_seeder import seed_categories
from models import User
from werkzeug.security import generate_password_hash

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
            print("Created admin user")
        print("✅ Database initialized and seeded successfully.")

if __name__ == "__main__":
    init_db()