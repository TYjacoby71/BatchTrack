
from flask import render_template
from models import Product
from . import products_bp

@products_bp.route('/')
def list_products():
    products = Product.query.all()
    return render_template('products/list_products.html', products=products)

@products_bp.route('/new')
def new_product():
    return render_template('products/new_product.html')
