
from flask import Blueprint, render_template
from app.routes.utils import load_data

products_bp = Blueprint("products", __name__)

@products_bp.route('/products')
def view_products():
    data = load_data()
    products = data.get("products", [])
    return render_template("products.html", products=products)

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
