from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime

update_stock_bp = Blueprint('update_stock', __name__)

@update_stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    if request.method == 'POST':
        data = load_data()
        # Process stock updates
        save_data(data)
        return redirect('/ingredients')
    return render_template('update_stock.html')