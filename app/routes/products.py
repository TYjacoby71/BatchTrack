
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
    
    # Aggregate products by name
    aggregated = defaultdict(lambda: {"yield": 0, "unit": None, "timestamps": []})
    for p in products:
        name = p["product"]
        try:
            qty = float(p["yield"])
            aggregated[name]["yield"] += qty
            aggregated[name]["unit"] = p["unit"]  # Assume same unit for same product
            aggregated[name]["timestamps"].append(p["timestamp"])
        except (ValueError, TypeError):
            continue
    
    # Convert to list format
    products_display = [
        {
            "product": name,
            "yield": str(details["yield"]),
            "unit": details["unit"],
            "timestamps": sorted(details["timestamps"], reverse=True)
        }
        for name, details in aggregated.items()
    ]
    
    return render_template("products.html", products=products_display)

@products_bp.route('/products/event/<int:product_idx>', methods=['POST'])
def log_product_event(product_idx):
    data = load_data()
    products = data.get("products", [])
    
    if product_idx >= len(products):
        return "Product not found", 404
        
    event_type = request.form.get('event_type')
    quantity = float(request.form.get('quantity', 0))
    method = request.form.get('method', '')
    note = request.form.get('note', '')
    
    # Log the event
    data.setdefault("product_events", []).append({
        "product": products[product_idx]["product"],
        "type": event_type,
        "quantity": quantity,
        "method": method,
        "note": note,
        "timestamp": datetime.now().isoformat()
    })
    
    # Update product quantity if needed
    try:
        current_qty = float(products[product_idx]["yield"])
        if current_qty >= quantity:
            products[product_idx]["yield"] = str(current_qty - quantity)
    except (ValueError, TypeError):
        pass
        
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
