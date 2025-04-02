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
    batches = data.get('batches', [])

    # Add batch IDs to products
    for product in products:
        if "batch_id" not in product: #Check for existence to avoid overwriting
            # Find matching batch
            batch = next((b for b in batches if b['recipe_name'] == product['product']), None)
            if batch:
                product['batch_id'] = batch['id']

    # Aggregate products by name with unit conversion
    from unit_converter import UnitConversionService
    service = UnitConversionService()
    aggregated = defaultdict(lambda: {"quantity": 0, "unit": None, "timestamps": []})

    for p in products:
        name = p["product"]
        try:
            # Get the base quantity from quantity_available
            base_qty = float(p.get("quantity_available", 0))

            # Process any recorded events
            for event in p.get("events", []):
                if event["type"] in ["sold", "spoiled", "sampled"]:
                    base_qty -= float(event["qty"])

            if not aggregated[name]["unit"]:
                # First entry sets the unit
                aggregated[name]["unit"] = p["unit"]
                aggregated[name]["quantity"] = base_qty
            else:
                if p["unit"] == aggregated[name]["unit"]:
                    # Same units, direct addition
                    aggregated[name]["quantity"] += base_qty
                else:
                    # Try conversion only for same type of measurements
                    converted_qty = service.convert(base_qty, p["unit"], aggregated[name]["unit"], material=name.lower())
                    if converted_qty is not None:
                        aggregated[name]["quantity"] += converted_qty
                    else:
                        # If units are incompatible, create separate entry
                        unique_name = f"{name} ({p['unit']})"
                        if not aggregated[unique_name]["unit"]:
                            aggregated[unique_name]["unit"] = p["unit"]
                            aggregated[unique_name]["quantity"] = base_qty
                        else:
                            aggregated[unique_name]["quantity"] += base_qty

            aggregated[name]["timestamps"].append(p["timestamp"])
        except (ValueError, TypeError) as e:
            print(f"Error processing product {name}: {e}")
            continue

    # Convert to list format
    products_display = [
        {
            "product": name,
            "yield": str(details["quantity"]),  # Use quantity for display
            "unit": details["unit"],
            "timestamps": sorted([(ts, next((b["id"] for b in data["batches"] 
                                           if b["timestamp"] == ts), None)) 
                                for ts in details["timestamps"]], reverse=True)
        }
        for name, details in aggregated.items()
    ]

    return render_template("products.html", products=products_display)

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
        new_quantity = available - quantity
        if new_quantity < 0:
            return "Cannot reduce quantity below 0", 400
        product["quantity_available"] = new_quantity

    product.setdefault("events", []).append({
        "type": event_type,
        "qty": quantity,
        "method": method,
        "note": note,
        "timestamp": datetime.now().isoformat()
    })

    save_data(data)
    return redirect("/products")


@products_bp.route('/products/delete/<string:timestamp>', methods=['POST'])
def delete_product(timestamp):
    data = load_data()
    products = data.get("products", [])
    # Find and remove the product with matching timestamp
    data["products"] = [p for p in products if p.get("timestamp") != timestamp]
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