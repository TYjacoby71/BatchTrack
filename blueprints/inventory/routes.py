
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryItem, Unit, IngredientCategory

def get_ingredient_categories():
    return IngredientCategory.query.order_by(IngredientCategory.name).all()

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/update', methods=['POST'])
@login_required
def update_inventory():
    items = request.form.to_dict(flat=False)
    errors = []
    success_count = 0
    
    for i in range(len(items.get('items[][id]', []))):
        item_id = items['items[][id]'][i]
        quantity = float(items['items[][quantity]'][i])
        from_unit = items['items[][unit]'][i]
        
        item = InventoryItem.query.get(item_id)
        if not item:
            errors.append(f"Item {item_id} not found")
            continue
            
        try:
            # Convert quantity to item's storage unit
            conversion = ConversionEngine.convert_units(
                quantity,
                from_unit,
                item.unit,
                ingredient_id=item.id,
                density=item.density or (item.category.default_density if item.category else None)
            )
            converted_qty = conversion['converted_value']
            item.quantity += converted_qty
            success_count += 1
            
        except ValueError as e:
            errors.append(f"Error updating {item.name}: {str(e)}")
            continue
    
    if success_count > 0:
        db.session.commit()
        
    if errors:
        flash('Some items could not be updated: ' + ' | '.join(errors), 'warning')
    if success_count:
        flash(f'{success_count} items updated successfully.', 'success')
        
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/add', methods=['POST'])
@login_required
def add_inventory():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    type = request.form.get('type')
    cost_per_unit = float(request.form.get('cost_per_unit', 0))
    
    item = InventoryItem(name=name, quantity=quantity, unit=unit, type=type, cost_per_unit=cost_per_unit)
    db.session.add(item)
    db.session.commit()
    flash('Inventory item added successfully.')
    return redirect(url_for('inventory.list_inventory'))

from utils.unit_utils import get_global_unit_list

@inventory_bp.route('/')
@login_required
def list_inventory():
    items = InventoryItem.query.all()
    units = Unit.query.all()
    return render_template('inventory_list.html', 
                         items=items,
                         units=units,
                         get_global_unit_list=get_global_unit_list)

@inventory_bp.route('/delete/<int:id>')
@login_required
def delete_inventory(id):
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Inventory item deleted successfully.')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/edit/ingredient/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_ingredient(id):
    item = InventoryItem.query.get_or_404(id)
    if item.type != 'ingredient':
        abort(404)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.quantity = float(request.form.get('quantity'))
        item.unit = request.form.get('unit')
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        item.category_id = request.form.get('category_id', None)
        if not item.category_id:  # Custom category selected
            item.density = float(request.form.get('density', 1.0))
        else:
            item.density = None  # Use category default
        db.session.commit()
        flash('Ingredient updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    from utils.unit_utils import get_global_unit_list
    return render_template('edit_ingredient.html', 
                         ing=item, 
                         get_ingredient_categories=get_ingredient_categories,
                         get_global_unit_list=get_global_unit_list)

@inventory_bp.route('/edit/container/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_container(id):
    item = InventoryItem.query.get_or_404(id)
    if item.type != 'container':
        abort(404)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.storage_amount = float(request.form.get('storage_amount'))
        item.storage_unit = request.form.get('storage_unit')
        item.quantity = float(request.form.get('quantity'))
        item.cost_per_unit = float(request.form.get('cost_per_unit', 0))
        db.session.commit()
        flash('Container updated successfully.')
        return redirect(url_for('inventory.list_inventory'))
    return render_template('edit_container.html', item=item)
