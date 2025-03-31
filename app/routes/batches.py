
from flask import Blueprint, render_template, request, redirect, jsonify
from datetime import datetime
from app.routes.utils import load_data, save_data, generate_qr_for_batch
from unit_converter import convert_units

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/check-stock-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    result = []

    if request.method == 'POST':
        demand = {}

        for recipe in data['recipes']:
            count = int(request.form.get(f"recipe_{recipe['id']}", 0))
            if count <= 0:
                continue
            for ing in recipe['ingredients']:
                name = ing['name']
                qty = float(ing['quantity']) * count
                unit = ing.get('unit', '')
                if name not in demand:
                    demand[name] = {'qty': 0, 'unit': unit}
                if unit == demand[name]['unit']:
                    demand[name]['qty'] += qty
                else:
                    converted_qty = convert_units(qty, unit, demand[name]['unit'])
                    if converted_qty is not None:
                        demand[name]['qty'] += converted_qty
                    else:
                        demand[name]['qty'] += qty

        for name, details in demand.items():
            match = next((i for i in data['ingredients'] if i['name'].lower() == name.lower()), None)
            if match and match.get('quantity'):
                available = float(match['quantity'])
                qty = details['qty']
                if match.get('unit') and details['unit'] and match['unit'] != details['unit']:
                    converted_qty = convert_units(qty, details['unit'], match['unit'])
                    if converted_qty is not None:
                        qty = converted_qty
                to_order = round(max(qty - available, 0.0), 2)
            else:
                available = 0.0
                to_order = details['qty']
            result.append({
                "name": name,
                "needed": round(details['qty'], 2),
                "available": round(available, 2),
                "status": "Insufficient" if to_order > 0 else "OK",
                "unit": match['unit'] if match and match.get('unit') else details['unit']
            })

    if result:
        return render_template('stock_bulk_result.html', stock_report=result)
    return render_template('check_stock_bulk.html', recipes=data['recipes'])

@batches_bp.route('/batches', methods=['GET'])
def view_batches():
    data = load_data()
    return render_template('batches.html', batches=data.get('batches', []))
