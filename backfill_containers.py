
from app import app, db
from models import BatchContainer

def backfill_containers():
    with app.app_context():
        # Get all containers where is_extra is NULL
        containers = BatchContainer.query.filter(BatchContainer.is_extra.is_(None)).all()
        
        print(f"Found {len(containers)} containers to update")
        
        # Update them to is_extra=False
        for container in containers:
            container.is_extra = False
        
        db.session.commit()
        print("✅ Successfully backfilled container data")

if __name__ == "__main__":
    backfill_containers()
