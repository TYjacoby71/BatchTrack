
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Product, ProductVariation
from flask_login import login_required

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def list_products():
    products = Product.query.all()
    return render_template('products/list_products.html', products=products)

@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = request.form['name']
        default_unit = request.form['default_unit']
        product = Product(name=name, default_unit=default_unit)
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('products.list_products'))
    return render_template('products/new_product.html')
