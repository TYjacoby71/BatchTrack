
from flask import Blueprint, render_template
from app.routes.utils import load_data

products_bp = Blueprint("products", __name__)

@products_bp.route('/products')
def view_products():
    data = load_data()
    products = data.get("products", [])
    return render_template("products.html", products=products)
