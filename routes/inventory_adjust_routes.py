
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Ingredient

adjust_bp = Blueprint('adjust', __name__)

@adjust_bp.route('/inventory/adjust', methods=['GET', 'POST'])
@login_required
def inventory_adjust():
    ingredients = Ingredient.query.all()

    if request.method == 'POST':
        ing_id = int(request.form.get('ingredient_id'))
        amount = float(request.form.get('adjustment'))
        reason = request.form.get('reason', 'Manual')
        ing = Ingredient.query.get(ing_id)
        if ing:
            ing.quantity += amount
            db.session.commit()
            flash(f"Adjusted {ing.name} by {amount} ({reason}).")
        return redirect(url_for('adjust.inventory_adjust'))

    return render_template('inventory_adjust.html', ingredients=ingredients)
