
from app import app, db
from models import User, Organization, Unit, IngredientCategory
from werkzeug.security import generate_password_hash

from seeders.unit_seeder import seed_units
from seeders.ingredient_category_seeder import seed_categories

def init_db():
    with app.app_context():
        db.create_all()
        seed_units()
        seed_categories()

        # Create default organization
        if not Organization.query.first():
            org = Organization(
                name="Jacob Boulette's Organization",
                subscription_tier='free'
            )
            db.session.add(org)
            db.session.flush()  # Get the ID
            
            # Create Jacob Boulette as first user
            if not User.query.filter_by(username='admin').first():
                jacob = User(
                    username='admin',
                    password_hash=generate_password_hash('admin'),
                    role='admin',
                    first_name='Jacob',
                    last_name='Boulette',
                    email='jacobboulette@outlook.com',
                    phone='775-934-5968',
                    organization_id=org.id
                )
                db.session.add(jacob)

        db.session.commit()
        print("✅ Database initialized with Jacob Boulette as admin user")

if __name__ == "__main__":
    init_db()
