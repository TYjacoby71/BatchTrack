
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime
import json

update_stock_bp = Blueprint('update_stock', __name__)

@update_stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()
    
    if request.method == 'POST':
        # Process stock updates
        save_data(data)
        return redirect('/ingredients')

    # Load units from JSON file
    with open('units.json') as f:
        units = json.load(f)
        
    return render_template('update_stock.html', 
                         ingredients=data.get('ingredients', []),
                         units=units)
