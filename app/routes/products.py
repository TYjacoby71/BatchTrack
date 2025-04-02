
from flask import Blueprint, render_template, request, redirect
from datetime import datetime
from app.routes.utils import load_data, save_data

products_bp = Blueprint("products", __name__)

@products_bp.route('/products')
def products():
    data = load_data()
    
    # Get all products from batches
    products_dict = {}
    
    for batch in data.get("batches", []):
        if "yield_qty" in batch and batch.get("finished", False):
            product_name = batch["recipe_name"]
            
            if product_name not in products_dict:
                products_dict[product_name] = {
                    "product": product_name,
                    "quantity_available": float(batch["yield_qty"]),
                    "unit": batch.get("yield_unit", ""),
                    "label_info": batch.get("label_info", ""),
                    "batch_id": batch["id"],
                    "timestamp": batch["timestamp"]
                }
            else:
                products_dict[product_name]["quantity_available"] += float(batch["yield_qty"])
                # Update batch ID and timestamp if this batch is more recent
                if batch["timestamp"] > products_dict[product_name]["timestamp"]:
                    products_dict[product_name]["batch_id"] = batch["id"]
                    products_dict[product_name]["timestamp"] = batch["timestamp"]

    products_list = list(products_dict.values())
    return render_template("products.html", products=products_list)

@products_bp.route('/products/event/<int:product_index>', methods=["POST"])
def log_product_event(product_index):
    data = load_data()
    products = []
    
    # Rebuild products list to match index
    products_dict = {}
    for batch in data.get("batches", []):
        if "yield_qty" in batch and batch.get("finished", False):
            product_name = batch["recipe_name"]
            if product_name not in products_dict:
                products_dict[product_name] = {
                    "product": product_name,
                    "quantity_available": float(batch["yield_qty"]),
                    "unit": batch.get("yield_unit", ""),
                    "batch_id": batch["id"]
                }
            else:
                products_dict[product_name]["quantity_available"] += float(batch["yield_qty"])
    
    products = list(products_dict.values())
    
    if product_index >= len(products):
        return "Invalid product index", 400
        
    product = products[product_index]
    event_type = request.form.get("event_type")
    quantity = float(request.form.get("quantity", 0))
    method = request.form.get("method", "")
    note = request.form.get("note", "")
    
    # Find all batches with this product and update quantities
    for batch in data["batches"]:
        if batch["recipe_name"] == product["product"] and batch.get("finished", False):
            if float(batch.get("yield_qty", 0)) > 0:
                batch["yield_qty"] = str(float(batch["yield_qty"]) - quantity)
                break
    
    # Log the event
    if "product_events" not in data:
        data["product_events"] = []
        
    data["product_events"].append({
        "product": product["product"],
        "type": event_type,
        "quantity": quantity,
        "method": method,
        "note": note,
        "timestamp": datetime.now().isoformat()
    })
    
    save_data(data)
    return redirect("/products")

@products_bp.route('/products/delete/<int:product_index>', methods=["POST"])
def delete_product(product_index):
    data = load_data()
    products = []
    
    # Rebuild products list to match index
    products_dict = {}
    for batch in data.get("batches", []):
        if "yield_qty" in batch and batch.get("finished", False):
            product_name = batch["recipe_name"]
            if product_name not in products_dict:
                products_dict[product_name] = batch["recipe_name"]
    
    products = list(products_dict.values())
    
    if product_index >= len(products):
        return "Invalid product index", 400
        
    product_name = products[product_index]
    
    # Set yield_qty to 0 for all batches of this product
    for batch in data["batches"]:
        if batch["recipe_name"] == product_name and batch.get("finished", False):
            batch["yield_qty"] = "0"
    
    save_data(data)
    return redirect("/products")

@products_bp.route('/products/export')
def export_products():
    data = load_data()
    products_dict = {}
    
    for batch in data.get("batches", []):
        if "yield_qty" in batch and batch.get("finished", False):
            product_name = batch["recipe_name"]
            if product_name not in products_dict:
                products_dict[product_name] = {
                    "product": product_name,
                    "quantity": float(batch["yield_qty"]),
                    "unit": batch.get("yield_unit", "")
                }
            else:
                products_dict[product_name]["quantity"] += float(batch["yield_qty"])

    csv_data = [["Product", "Quantity", "Unit"]]
    for product in products_dict.values():
        csv_data.append([
            product["product"],
            str(product["quantity"]),
            product["unit"]
        ])
    
    output = "\n".join([",".join(row) for row in csv_data])
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=products.csv"}
    )
