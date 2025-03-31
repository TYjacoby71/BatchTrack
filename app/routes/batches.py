from flask import Blueprint, render_template, request, redirect, Response, session, jsonify
import json
from datetime import datetime
from app.routes.utils import load_data, save_data, generate_qr_for_batch

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/batches')
def view_batches():
    from datetime import datetime

    data = load_data()
    batches = data.get('batches', [])

    # Filters
    tag_filter = request.args.get("tag", "").lower()
    recipe_filter = request.args.get("recipe", "").lower()

    if tag_filter:
        batches = [b for b in batches if any(tag_filter in t.lower() for t in b.get("tags", []))]

    if recipe_filter:
        batches = [b for b in batches if recipe_filter in b.get("recipe_name", "").lower()]

    # Sort newest first
    batches = sorted(batches, key=lambda b: b["timestamp"], reverse=True)

    # Format timestamps
    for batch in batches:
        if batch.get("timestamp"):
            batch["timestamp"] = datetime.fromisoformat(batch["timestamp"]).strftime("%b %d, %Y at %I:%M %p")

    return render_template('batches.html', batches=batches)

@batches_bp.route('/')
def dashboard():
    from datetime import datetime

    data = load_data()
    low_stock = []
    
    # Load ingredients and check stock levels
    for i in data.get('ingredients', []):
        qty = i.get('quantity', '')
        try:
            if qty == '' or (isinstance(qty, (int, float, str)) and float(str(qty)) < 10):
                low_stock.append(i)
                print(f"Adding to low stock: {i['name']} - Qty: {qty}")
        except (ValueError, TypeError) as e:
            print(f"Error processing {i['name']}: {e}")
            low_stock.append(i)
    
    print(f"Total low stock items: {len(low_stock)}")
    recent_batches = sorted(data.get('batches', []), key=lambda b: b['timestamp'], reverse=True)[:5]

    # Format timestamps
    for batch in recent_batches:
        if batch.get('timestamp'):
            dt = datetime.fromisoformat(batch['timestamp'])
            batch['formatted_time'] = dt.strftime('%B %d, %Y at %I:%M %p')

    return render_template("dashboard.html", low_stock=low_stock, recent_batches=recent_batches)

@batches_bp.route('/check-stock-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()

    if request.method == 'POST':
        recipe_ids = request.form.getlist('recipe_id')
        batch_counts = request.form.getlist('batch_count')
        usage = {}

        for r_id, count in zip(recipe_ids, batch_counts):
            count = float(count or 0)
            if count > 0:
                recipe = next((r for r in data['recipes'] if r['id'] == int(r_id)), None)
                if recipe:
                    for item in recipe['ingredients']:
                        qty = float(item['quantity']) * count
                        usage[item['name']] = usage.get(item['name'], 0) + qty

        stock_report = []
        for name, needed in usage.items():
            current = next((i for i in data['ingredients'] if i['name'].lower() == name.lower()), None)
            current_qty = float(current['quantity']) if current else 0
            stock_report.append({
                "name": name,
                "needed": round(needed, 2),
                "available": round(current_qty, 2),
                "unit": current['unit'] if current else 'units',
                "status": "OK" if current_qty >= needed else "LOW"
            })

        return render_template('stock_bulk_result.html', stock_report=stock_report)

    return render_template('check_stock_bulk.html', recipes=data['recipes'])

@batches_bp.route('/tags.json')
def tag_suggestions():
    try:
        with open("tags.json") as f:
            tags = json.load(f)
    except:
        tags = []
    return jsonify(tags)

@batches_bp.route('/batches/export')
def export_batches():
    from datetime import datetime
    from flask import Response

    data = load_data()
    batches = data.get('batches', [])

    # Generate CSV
    lines = ["id,recipe_name,date,total_cost,tags"]
    for b in batches:
        recipe_name = b['recipe_name'].replace('"', '""')
        tags = '","'.join(b.get('tags', []))
        line = f"{b['id']},\"{recipe_name}\",{b['timestamp']},{b.get('total_cost', 0)},\"{tags}\""
        lines.append(line)

    content = "\n".join(lines)
    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=batches.csv'}
    )

@batches_bp.route('/tags.json')
def get_tags():
    data = load_data()
    tags = set()
    for batch in data.get('batches', []):
        tags.update(batch.get('tags', []))
    return jsonify(sorted(list(tags)))

@batches_bp.route('/tags/manage', methods=['GET', 'POST'])
def tag_admin():
    data = load_data()
    tag_counts = {}

    for batch in data.get("batches", []):
        for tag in batch.get("tags", []):
            tag = tag.strip().lower()
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if request.method == 'POST':
        action = request.form.get("action")
        old_tag = request.form.get("old_tag", "").strip().lower()
        new_tag = request.form.get("new_tag", "").strip().lower()

        if action == 'merge' and old_tag and new_tag:
            for batch in data["batches"]:
                if "tags" in batch:
                    batch["tags"] = [new_tag if t.strip().lower() == old_tag else t for t in batch["tags"]]
            save_data(data)

        elif action == 'delete' and old_tag:
            for batch in data["batches"]:
                if "tags" in batch:
                    batch["tags"] = [t for t in batch["tags"] if t.strip().lower() != old_tag]
            save_data(data)

        return redirect('/tags/manage')

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return render_template("tags_manage.html", tags=sorted_tags)


@batches_bp.route('/batches/<batch_id>/favorite')
def toggle_favorite(batch_id):
    data = load_data()
    for batch in data["batches"]:
        if str(batch["id"]) == str(batch_id):
            tags = batch.get("tags", [])
            if "favorite" in tags:
                tags.remove("favorite")
            else:
                tags.append("favorite")
            batch["tags"] = tags
            break
    save_data(data)
    return redirect("/batches")

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

        # Deduct ingredients
        for item in recipe['ingredients']:
            for ing in data['ingredients']:
                if ing['name'] == item['name']:
                    ing_qty = to_float(ing['quantity'])
                    used_qty = to_float(item['quantity'])
                    ing['quantity'] = str(round(ing_qty - used_qty, 2))
                    break


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
@batches_bp.route('/ingredients/usage')
def ingredient_usage():
    data = load_data()
    usage = {}

    def to_float(v):
        try:
            return float(v)
        except:
            return 0

    for batch in data.get("batches", []):
        for ing in batch.get("ingredients", []):
            name = ing["name"]
            qty = to_float(ing["quantity"])
            usage[name] = usage.get(name, 0) + qty

    sorted_usage = sorted(usage.items(), key=lambda x: x[1], reverse=True)
    return render_template("ingredient_usage.html", usage=sorted_usage)

@batches_bp.route('/batches/<batch_id>/print')
def print_batch(batch_id):
    data = load_data()
    batch = next((b for b in data.get("batches", []) if b["id"] == batch_id), None)
    if not batch:
        return "Batch not found", 404
    return render_template("batch_print.html", batch=batch)

@batches_bp.route('/download-purchase-list')
def download_purchase_list():
    try:
        data = load_data()
        ingredients = data.get('ingredients', [])

        lines = ["name,quantity,unit,cost_per_unit"]
        for ing in ingredients:
            name = ing.get('name', '').replace(',', ' ')
            quantity = ing.get('quantity', '')
            unit = ing.get('unit', '')
            cost = ing.get('cost_per_unit', '0.00')
            lines.append(f"{name},{quantity},{unit},{cost}")

        csv_content = "\n".join(lines)
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=purchase_list.csv'}
        )
    except Exception as e:
        return f"Error generating purchase list: {str(e)}", 500

@batches_bp.route('/batches/<batch_id>/edit-notes', methods=['GET', 'POST'])
def edit_batch_notes(batch_id):
    data = load_data()
    batch = next((b for b in data['batches'] if str(b['id']) == str(batch_id)), None)

    if not batch:
        return "Batch not found", 404

    if request.method == 'POST':
        batch['notes'] = request.form.get("notes", "").strip()
        batch['tags'] = [t.strip().lower() for t in request.form.get("tags", "").split(",") if t.strip()]
        save_data(data)
        return redirect('/batches')

    return render_template("edit_batch_notes.html", batch=batch)

@batches_bp.route('/batches/<batch_id>/repeat')
def repeat_batch(batch_id):
    from datetime import datetime
    data = load_data()
    original = next((b for b in data["batches"] if str(b["id"]) == str(batch_id)), None)
    if not original:
        return "Batch not found", 404

    new_batch = original.copy()
    new_batch['id'] = len(data['batches']) + 1 
    new_batch['timestamp'] = datetime.utcnow().isoformat()
    if 'tags' in new_batch:
        new_batch['tags'].append('repeat')
    else:
        new_batch['tags'] = ['repeat']

    data["batches"].append(new_batch)
    save_data(data)
    return redirect("/batches")