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

    # Aggregate products by name with unit conversion
    from unit_converter import convert_units
    aggregated = defaultdict(lambda: {"yield": 0, "unit": None, "timestamps": []})
    for p in products:
        name = p["product"]
        try:
            qty = float(p["yield"])
            if not aggregated[name]["unit"]:
                # First entry sets the unit
                aggregated[name]["unit"] = p["unit"]
                aggregated[name]["yield"] = qty
            else:
                # Convert subsequent quantities to first unit
                converted_qty = convert_units(qty, p["unit"], aggregated[name]["unit"])
                if converted_qty is not None:
                    aggregated[name]["yield"] += converted_qty
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
    available = product.get("quantity_available", 0)

    if event_type in ("sold", "spoiled", "sampled"):
        if available < quantity:
            return f"Not enough inventory to {event_type} {quantity} units.", 400
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