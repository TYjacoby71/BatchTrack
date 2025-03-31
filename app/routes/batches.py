from flask import Blueprint, render_template, request
from app.routes.utils import load_data, save_data, generate_qr_for_batch
from datetime import datetime

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/check-stock-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    result = []

    def to_float(val):
        try:
            return float(val.strip())
        except:
            return 0.0

    if request.method == 'POST':
        recipe_ids = request.form.getlist('recipe_id')
        batch_counts = request.form.getlist('batch_count')
        usage = {}

        for r_id, count in zip(recipe_ids, batch_counts):
            recipe = next((r for r in data['recipes'] if str(r['id']) == r_id), None)
            if recipe:
                for item in recipe['ingredients']:
                    qty = to_float(item['quantity']) * to_float(count)
                    usage[item['name']] = usage.get(item['name'], 0) + qty

        stock_report = []
        for name, needed in usage.items():
            current = next((i for i in data['ingredients'] if i['name'] == name), {"quantity": "0"})
            current_qty = to_float(current['quantity'])
            stock_report.append({
                "name": name,
                "needed": round(needed, 2),
                "available": round(current_qty, 2),
                "status": "OK" if current_qty >= needed else "LOW"
            })

        return render_template('stock_bulk_result.html', stock_report=stock_report)

    return render_template('check_stock_bulk.html', recipes=data['recipes'])

@batches_bp.route('/batches')
def batches():
    data = load_data()
    return render_template('batches.html', batches=data['batches'])