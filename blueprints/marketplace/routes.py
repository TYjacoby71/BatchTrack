
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from . import marketplace_bp

@marketplace_bp.route('/products')
@login_required
def list_products():
    """List marketplace products"""
    return render_template('marketplace/products.html')

@marketplace_bp.route('/orders')
@login_required
def orders():
    """View marketplace orders"""
    return render_template('marketplace/orders.html')
