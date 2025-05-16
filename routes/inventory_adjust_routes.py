from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryItem

adjust_bp = Blueprint('adjust', __name__)

@adjust_bp.route('/inventory/adjust', methods=['GET', 'POST'])
@login_required
def inventory_adjust():
    ingredients = InventoryItem.query.all()
    units = [ing.unit for ing in ingredients]
    units = list(set(units))  # Get unique units

    if request.method == 'POST':
        ing_id = int(request.form.get('ingredient_id'))
        amount = float(request.form.get('adjustment'))
        unit = request.form.get('unit')
        reason = request.form.get('reason')
        
        ing = InventoryItem.query.get(ing_id)
        if ing:
            try:
                # Convert amount to item's storage unit if needed
                if unit != ing.unit:
                    conversion = ConversionEngine.convert_units(
                        amount,
                        unit,
                        ing.unit,
                        ingredient_id=ing.id
                    )
                    amount = conversion['converted_value']
                
                # Spoil and Trash are subtractions
                if reason in ['spoil', 'trash']:
                    amount = -abs(amount)
                
                ing.quantity += amount
                db.session.commit()
                flash(f"Adjusted {ing.name} by {amount} {ing.unit} ({reason}).", 'success')
            except Exception as e:
                flash(f"Error adjusting inventory: {str(e)}", 'error')
        return redirect(url_for('adjust.inventory_adjust'))

    return render_template('inventory_adjust.html', ingredients=ingredients, units=units)