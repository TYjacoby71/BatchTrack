
from flask import Blueprint, render_template, request, redirect, Response
from datetime import datetime
from app.routes.utils import load_data, save_data, generate_qr_for_batch

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

@batches_bp.route('/start-batch/<int:recipe_id>', methods=['GET', 'POST'])
def start_batch(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    if request.method == 'POST':
        def to_float(val):
            try:
                return float(val.strip())
            except:
                return 0.0

        insufficient = []
        for item in recipe['ingredients']:
            inv_item = next((i for i in data['ingredients'] if i['name'] == item['name']), None)
            if not inv_item or to_float(inv_item['quantity']) < to_float(item['quantity']):
                insufficient.append(item['name'])

        if insufficient:
            return f"Insufficient stock for: {', '.join(insufficient)}", 400

        for item in recipe['ingredients']:
            for ing in data['ingredients']:
                if ing['name'] == item['name']:
                    ing_qty = to_float(ing['quantity'])
                    used_qty = to_float(item['quantity'])
                    ing['quantity'] = str(round(ing_qty - used_qty, 2))

        notes = request.form.get('notes', '').strip()
        tags = request.form.get('tags', '').strip().split(',')

        data['batch_counter'] = data.get('batch_counter', 0) + 1
        batch_id = f"batch_{data['batch_counter']}"

        total_cost = 0.0
        for item in recipe['ingredients']:
            inv_item = next((i for i in data['ingredients'] if i['name'] == item['name']), None)
            if inv_item:
                cost = float(inv_item.get('cost_per_unit', 0)) * float(item['quantity'])
                total_cost += cost

        qr_path = generate_qr_for_batch(batch_id)

        new_batch = {
            "id": batch_id,
            "recipe_id": recipe['id'],
            "recipe_name": recipe['name'],
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes,
            "tags": tags,
            "ingredients": recipe['ingredients'],
            "total_cost": round(total_cost, 2),
            "qr_code": qr_path
        }

        data.setdefault('batches', []).append(new_batch)
        save_data(data)
        return redirect('/batches')

    return render_template('start_batch.html', recipe=recipe)

@batches_bp.route('/batches')
def view_batches():
    data = load_data()
    batches = data.get('batches', [])
    
    tag_filter = request.args.get("tag", "").lower()
    recipe_filter = request.args.get("recipe", "").lower()

    if tag_filter:
        batches = [b for b in batches if any(tag_filter in t.lower() for t in b.get("tags", []))]

    if recipe_filter:
        batches = [b for b in batches if recipe_filter in b.get("recipe_name", "").lower()]

    return render_template('batches.html', batches=batches)

@batches_bp.route('/download-purchase-list')
def download_purchase_list():
    data = load_data()
    ingredients = data.get('ingredients', [])

    lines = ["name,quantity,unit"]
    for ing in ingredients:
        lines.append(f"{ing['name']},{ing['quantity']},{ing['unit']}")

    csv_content = "\n".join(lines)
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=purchase_list.csv'}
    )
