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
    product_filter = request.args.get("product", "").lower()

    if tag_filter:
        batches = [b for b in batches if any(tag_filter in t.lower() for t in b.get("tags", []))]

    if recipe_filter:
        batches = [b for b in batches if recipe_filter in b.get("recipe_name", "").lower()]

    if product_filter:
        # Get all batches for this product
        batches = [b for b in batches if product_filter == b.get("recipe_name", "").lower()]
        # Sort by timestamp descending (newest first)
        batches = sorted(batches, key=lambda x: x.get("timestamp", ""), reverse=True)

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
    ingredients = data.get('ingredients', [])

    low_stock = []
    for ing in ingredients:
        print(f"Checking ingredient: {ing['name']} → quantity: {ing['quantity']}")
        try:
            qty = float(ing.get("quantity", 0))
            if qty < 10:
                print(f"⚠️ Low stock: {ing['name']} at {qty}")
                low_stock.append(ing)
        except Exception as e:
            print(f"Error parsing quantity for {ing.get('name', '?')}: {e}")

    print(f"Found {len(low_stock)} low stock ingredients.")

    # Get recent batches (sorted newest first)
    recent_batches = sorted(
        data.get("batches", []),
        key=lambda b: b.get("timestamp", ""),
        reverse=True
    )[:5]

    # Format timestamps
    for batch in recent_batches:
        if batch.get('timestamp'):
            dt = datetime.fromisoformat(batch['timestamp'])
            batch['formatted_time'] = dt.strftime('%B %d, %Y at %I:%M %p')

    return render_template("dashboard.html", low_stock=low_stock, recent_batches=recent_batches)

from unit_converter import can_fulfill
from app.error_tools import safe_route

@batches_bp.route('/check-stock-bulk', methods=['GET', 'POST'])
@safe_route
def check_stock_bulk():
    data = load_data()
    inventory = data.get("ingredients", [])
    recipes = data.get("recipes", [])

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
                        # Get base quantity for one batch
                        base_qty = float(item['quantity'])
                        # Calculate total needed for all batches
                        total_qty = base_qty * count
                        # Store with unit for conversion later
                        if item['name'] not in usage:
                            usage[item['name']] = {
                                'qty': total_qty,
                                'unit': item.get('unit', 'units')
                            }
                        else:
                            # Add to existing quantity in same unit
                            usage[item['name']]['qty'] += total_qty

        stock_report = []
        from unit_converter import check_stock_availability

        for name, details in usage.items():
            current = next((i for i in data['ingredients'] if i['name'].lower() == name.lower()), None)
            try:
                if not current or not current.get('quantity'):
                    raise ValueError("No stock found")

                check = check_stock_availability(
                    details['qty'],
                    details['unit'],
                    current['quantity'],
                    current['unit'],
                    material=name.lower()
                )

                stock_report.append({
                    "name": name,
                    "needed": f"{round(details['qty'], 2)} {details['unit']}",
                    "available": f"{check['converted']} {check['unit']}",
                    "status": check['status']
                })
            except (ValueError, TypeError):
                stock_report.append({
                    "name": name,
                    "needed": details['qty'],
                    "available": 0,
                    "unit": details['unit'],
                    "status": "LOW"
                })

        # Calculate missing items summary
        from collections import defaultdict
        from app.unit_conversion import convert_unit

        needed_items = defaultdict(lambda: {"total": 0, "unit": ""})

        for item in stock_report:
            if item["status"] == "LOW":
                name = item["name"]
                needed = item["needed"]
                available = item["available"]
                unit = item["unit"]

                shortfall = max(needed - available, 0)
                needed_items[name]["total"] += shortfall
                needed_items[name]["unit"] = unit

        return render_template('bulk_stock_results.html', stock_report=stock_report, missing_summary=needed_items)

    return render_template('bulk_stock_check.html', recipes=data['recipes'])

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
    from flask import flash
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    # Check stock before allowing batch creation
    inventory = data.get("ingredients", [])
    has_low_stock = False
    for item in recipe.get("ingredients", []):
        match = next((i for i in inventory if i["name"].lower() == item["name"].lower()), None)
        if not match:
            has_low_stock = True
            break
        try:
            check = check_stock_availability(
                float(item["quantity"]), item.get("unit", "units"),
                float(match["quantity"]), match.get("unit", "units"),
                material=item["name"].lower()
            )
            if check["status"] == "LOW":
                has_low_stock = True
                break
        except (ValueError, TypeError):
            has_low_stock = True
            break

    if has_low_stock:
        flash("Cannot start batch due to insufficient stock. Please check inventory levels.", "error")
        return redirect(f'/stock/check/{recipe_id}')

    if request.method == 'POST':
        # Check if we have sufficient stock
        from unit_converter import UnitConversionService
        service = UnitConversionService()
        inventory = data.get("ingredients", [])
        insufficient = []
        scale = float(request.form.get('scale', 1))

        for item in recipe['ingredients']:
            ing_name = item["name"]
            req_qty = float(item["quantity"]) * scale
            req_unit = item.get("unit", "").lower().strip()

            match = next((i for i in inventory if i["name"].lower() == ing_name.lower()), None)
            if not match:
                insufficient.append(f"{ing_name} (not in stock)")
                continue

            inv_unit = match.get("unit", "").lower().strip()
            inv_qty = float(match.get("quantity", 0))

            if inv_unit != req_unit:
                converted = service.convert(req_qty, req_unit, inv_unit, material=ing_name.lower())
                if converted is not None:
                    req_qty = converted
                else:
                    insufficient.append(f"{ing_name} (unit conversion error)")
                    continue

            if inv_qty < req_qty:
                insufficient.append(f"{ing_name} (need {req_qty} {req_unit}, have {inv_qty} {inv_unit})")

        if insufficient:
            from flask import flash
            flash(f"Cannot start batch. Insufficient ingredients: {', '.join(insufficient)}")
            return redirect(f'/stock/check/{recipe_id}')

        notes = request.form.get('notes', '').strip()
        tags = request.form.get('tags', '').strip().split(',')
        scale = float(request.form.get('scale', 1))

        data['batch_counter'] = data.get('batch_counter', 0) + 1
        batch_id = f"batch_{data['batch_counter']}"

        # Scale recipe ingredients
        scaled_ingredients = []
        total_cost = 0.0
        for item in recipe['ingredients']:
            scaled_qty = float(item['quantity']) * scale
            scaled_ingredients.append({
                'name': item['name'],
                'quantity': scaled_qty,
                'unit': item.get('unit', '')
            })
            inv_item = next((i for i in data['ingredients'] if i['name'] == item['name']), None)
            if inv_item:
                try:
                    cost_per_unit = float(inv_item.get('cost_per_unit', '') or 0)
                    quantity = float(item.get('quantity', '') or 0) * scale
                    cost = cost_per_unit * quantity
                    total_cost += cost
                except ValueError:
                    # If conversion fails, treat as 0
                    cost = 0
                    total_cost += cost

        qr_path = generate_qr_for_batch(batch_id)

        new_batch = {
            "id": batch_id,
            "recipe_id": recipe['id'],
            "recipe_name": recipe['name'],
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes,
            "tags": tags,
            "ingredients": scaled_ingredients,
            "scale": scale,
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
    data = load_data()
    batch = next((b for b in data["batches"] if str(b["id"]) == str(batch_id)), None)
    if not batch:
        return "Batch not found", 404

    recipe = next((r for r in data['recipes'] if r['id'] == batch['recipe_id']), None)
    if not recipe:
        return "Recipe not found", 404

    return redirect(f"/start-batch/{recipe['id']}")

@batches_bp.route('/batches/view/<batch_id>')
def view_batch(batch_id):
    data = load_data()
    batch = next((b for b in data.get("batches", []) if str(b["id"]) == str(batch_id)), None)
    if not batch:
        return "Batch not found", 404
    return render_template("view_batch.html", batch=batch)

@batches_bp.route('/batches/delete/<batch_id>')
def delete_batch(batch_id):
    data = load_data()
    # Simply remove the batch from the list without affecting inventory
    data['batches'] = [b for b in data['batches'] if str(b['id']) != str(batch_id)]
    save_data(data)
    return redirect('/batches')

@batches_bp.route('/batches/bulk-delete', methods=['POST'])
def bulk_delete_batches():
    batch_ids = request.form.getlist('batch_ids')
    if not batch_ids:
        return redirect('/batches')

    data = load_data()
    data['batches'] = [b for b in data['batches'] if str(b['id']) not in batch_ids]
    save_data(data)
    return redirect('/batches')

@batches_bp.route('/batches/update-notes/<batch_id>', methods=['POST'])
def update_batch_notes(batch_id):
    data = load_data()
    batch = next((b for b in data['batches'] if str(b['id']) == str(batch_id)), None)
    if batch:
        batch['notes'] = request.form.get('notes', '').strip()
        save_data(data)
    return redirect(f'/batches/view/{batch_id}')

@batches_bp.route('/batches/invalidate/<batch_id>', methods=["POST"])
def invalidate_batch(batch_id):
    data = load_data()
    batches = data.get("batches", [])
    recipes = data.get("recipes", [])
    inventory = data.get("ingredients", [])

    batch = next((b for b in batches if str(b['id']) == str(batch_id)), None)
    if not batch:
        return "Batch not found", 404

    recipe_name = batch.get("recipe_name")
    matched_recipe = next((r for r in recipes if r["name"] == recipe_name), None)

    if not matched_recipe:
        return "Recipe not found", 404

    for item in matched_recipe["ingredients"]:
        found = next((inv for inv in inventory if inv["name"] == item["name"]), None)
        if found:
            try:
                found["quantity"] = float(found.get("quantity", 0)) + float(item["quantity"])
            except ValueError:
                continue
        else:
            inventory.append({
                "name": item["name"],
                "quantity": float(item["quantity"]),
                "unit": item.get("unit", ""),
                "cost_per_unit": 0,
            })

    batches.remove(batch)
    data["ingredients"] = inventory
    data["batches"] = batches
    save_data(data)

    return redirect("/batches")

@batches_bp.route('/batches/finish/<batch_id>', methods=["GET", "POST"])
def finish_batch(batch_id):
    from unit_converter import UnitConversionService
    service = UnitConversionService()
    from datetime import datetime

    data = load_data()
    batches = data.get("batches", [])
    inventory = data.get("ingredients", [])
    products = data.setdefault("products", [])
    recipes = data.get("recipes", [])

    batch = next((b for b in batches if str(b['id']) == str(batch_id)), None)
    if not batch:
        return "Batch not found", 404
    recipe = next((r for r in recipes if r["name"] == batch.get("recipe_name")), None)

    if request.method == "POST":
        # Handle ingredient usage adjustments
        ingredient_names = request.form.getlist("ingredient_name[]")
        quantities_used = request.form.getlist("quantity_used[]")

        # Process each ingredient adjustment
        for name, qty_used_str in zip(ingredient_names, quantities_used):
            try:
                qty_used = float(qty_used_str)
                ingredient = next((i for i in inventory if i["name"].lower() == name.lower()), None)
                if ingredient:
                    recipe_ingredient = next((ri for ri in batch["ingredients"] if ri["name"].lower() == name.lower()), None)
                    if recipe_ingredient:
                        # Only update if quantity used is different from recipe
                        if qty_used != float(recipe_ingredient["quantity"]):
                            inv_qty = float(ingredient["quantity"])
                            # Calculate the difference and adjust inventory
                            qty_diff = float(recipe_ingredient["quantity"]) - qty_used
                            ingredient["quantity"] = inv_qty + qty_diff
                            # Log the adjustment
                            data.setdefault("inventory_log", []).append({
                                "name": name,
                                "change": qty_diff,
                                "unit": ingredient["unit"],
                                "reason": "Batch Usage Adjustment",
                                "timestamp": datetime.now().isoformat()
                            })
            except ValueError:
                continue

    if request.method == "POST":
        batch_type = request.form.get("batch_type")
        success = request.form.get("success")
        notes = request.form.get("notes")
        yield_qty = float(request.form.get("yield_qty"))
        yield_unit = request.form.get("yield_unit")

        batch.update({
            "completed": True,
            "batch_type": batch_type,
            "success": success,
            "notes": notes,
            "yield_qty": yield_qty,
            "yield_unit": yield_unit
        })

        if success == "yes" and recipe:
            for ingredient in recipe["ingredients"]:
                ing_name = ingredient["name"]
                req_qty = float(ingredient["quantity"])
                req_unit = ingredient.get("unit", "").lower().strip()

                match = next((i for i in inventory if i["name"].lower() == ing_name.lower()), None)
                if match:
                    inv_unit = match.get("unit", "").lower().strip()
                    inv_qty = float(match["quantity"])
                    if inv_unit != req_unit:
                        try:
                            converted = service.convert(req_qty, req_unit, inv_unit)
                            if converted is not None:
                                req_qty = converted
                            else:
                                continue
                        except (ValueError, TypeError):
                            continue
                    match["quantity"] = max(inv_qty - req_qty, 0)

            if batch_type == "product":
                # Find existing product
                existing = next((p for p in products if p["product"].lower() == batch["recipe_name"].lower() and p["unit"] == yield_unit), None)

                if existing:
                    # Add to total quantity and update timestamp/batch
                    if "quantity_available" not in existing:
                        existing["quantity_available"] = float(existing.get("yield", 0))
                    existing["quantity_available"] = float(existing["quantity_available"]) + float(yield_qty)
                    existing["yield"] = float(yield_qty)  # Update yield with latest batch
                    existing["timestamp"] = datetime.now().isoformat()
                    existing["batch_id"] = batch_id  # Update batch_id reference
                else:
                    new_product = {
                        "product": batch["recipe_name"],
                        "yield": float(yield_qty),
                        "unit": yield_unit,
                        "notes": notes,
                        "label_info": request.form.get("label_info", ""),
                        "timestamp": datetime.now().isoformat(),
                        "quantity_available": float(yield_qty),
                        "events": [],
                        "batch_id": batch_id
                    }
                    products.append(new_product)
            else:  # inventory type
                inv_item = {
                    "name": batch["recipe_name"],
                    "quantity": yield_qty,
                    "unit": yield_unit,
                    "cost_per_unit": 0,
                }
                inventory.append(inv_item)

        save_data(data)
        return redirect("/products")

    return render_template("finish_batch.html", batch=batch, batch_id=batch_id)