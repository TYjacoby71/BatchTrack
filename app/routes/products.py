from flask import Blueprint, render_template, Response, request, redirect
import csv
from datetime import datetime
from collections import defaultdict
from app.routes.utils import load_data, save_data

products_bp = Blueprint("products", __name__)

@products_bp.route('/products')
def view_products():
    data = load_data()
    products = data.get("products", [])
    return render_template("products.html", products=products)

@products_bp.route('/products/event/<int:product_index>', methods=["POST"])
def product_event(product_index):
    data = load_data()
    products = data.get("products", [])
    if product_index >= len(products):
        return "Product not found", 404

    event_type = request.form.get("event_type")
    quantity = request.form.get("quantity", type=int)
    method = request.form.get("method", "")
    note = request.form.get("note", "")

    if quantity <= 0:
        return "Invalid quantity", 400

    product = products[product_index]
    available = float(product.get("yield", 0))  # Use yield as initial quantity
    if "quantity_available" not in product:
        product["quantity_available"] = available

    available = float(product["quantity_available"])
    if event_type in ("sold", "spoiled", "sampled"):
        if available < quantity:
            return f"Not enough inventory to {event_type} {quantity} units. Only {available} available.", 400
            
        # Get all batches for this product
        batches = data.get("batches", [])
        product_batches = [b for b in batches 
                         if b.get("recipe_name") == product["product"] 
                         and b.get("completed") 
                         and b.get("success") == "yes"]
        
        # Sort by timestamp (oldest first)
        product_batches.sort(key=lambda x: x.get("timestamp", ""))
        
        remaining = quantity
        for batch in product_batches:
            if not batch.get("remaining_qty"):
                batch["remaining_qty"] = float(batch.get("yield_qty", 0))
            
            if batch["remaining_qty"] > 0:
                deduct = min(remaining, batch["remaining_qty"])
                batch["remaining_qty"] -= deduct
                remaining -= deduct
                
            if remaining <= 0:
                break
                
        product["quantity_available"] = available - quantity

    product.setdefault("events", []).append({
        "type": event_type,
        "qty": quantity,
        "method": method,
        "note": note,
        "timestamp": datetime.now().isoformat()
    })

    save_data(data)
    return redirect("/products")


@products_bp.route('/products/delete/<int:product_index>', methods=['POST'])
def delete_product(product_index):
    data = load_data()
    products = data.get("products", [])
    if product_index < len(products):
        del products[product_index]
        data["products"] = products
        save_data(data)
    return redirect('/products')

@products_bp.route('/products/export')
def export_products():
    data = load_data()
    products = data.get("products", [])
    fieldnames = ["product", "yield", "unit", "notes", "label_info", "timestamp"]
    output = Response()
    output.headers["Content-Disposition"] = "attachment; filename=products.csv"
    output.headers["Content-type"] = "text/csv"
    writer = csv.DictWriter(output.stream, fieldnames=fieldnames)
    writer.writeheader()
    for item in products:
        writer.writerow({field: item.get(field, "") for field in fieldnames})
    return output