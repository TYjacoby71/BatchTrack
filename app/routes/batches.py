
from flask import Blueprint, render_template, request, redirect, Response
from datetime import datetime
from app.routes.utils import load_data, save_data, generate_qr_for_batch

batches_bp = Blueprint('batches', __name__)

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
    return render_template('batches.html', batches=data.get('batches', []))

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
