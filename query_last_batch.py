
from app import app, db
from models import Batch, BatchIngredient, BatchContainer, ProductInventory
from datetime import datetime

with app.app_context():
    # Get the most recent completed batch
    last_batch = Batch.query.order_by(Batch.completed_at.desc()).first()

    if last_batch:
        print(f"\nBatch Details:")
        print(f"Label Code: {last_batch.label_code}")
        print(f"Recipe: {last_batch.recipe.name}")
        print(f"Status: {last_batch.status}")
        print(f"Started: {last_batch.started_at}")
        print(f"Completed: {last_batch.completed_at}")
        print(f"Type: {last_batch.batch_type}")
        print(f"Final Quantity: {last_batch.final_quantity} {last_batch.output_unit}")
        print(f"Perishable: {'Yes' if last_batch.is_perishable else 'No'}")
        print(f"Shelf Life: {last_batch.shelf_life_days if last_batch.shelf_life_days else 'N/A'} days")
        print(f"Expiration Date: {last_batch.expiration_date.strftime('%Y-%m-%d') if last_batch.expiration_date else 'N/A'}")

        # Show ingredients used
        print("\nIngredients Used:")
        for ing in last_batch.ingredients:
            print(f"- {ing.amount_used} {ing.unit} of {ing.ingredient.name}")

        # Show containers used  
        print("\nContainers Used:")
        for cont in last_batch.containers:
            print(f"- {cont.quantity_used} of {cont.container.name}")

        # If it was a product batch, show inventory created
        if last_batch.batch_type == 'product':
            inventory = ProductInventory.query.filter_by(batch_id=last_batch.id).first()
            if inventory:
                print(f"\nProduct Inventory Created:")
                print(f"Product: {inventory.product.name}")
                print(f"Quantity: {inventory.quantity} {inventory.unit}")
    else:
        print("No completed batches found")
