
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, InventoryUnit

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    quantity = db.Column(db.Float)
    unit = db.Column(db.String(32))

ingredients_bp = Blueprint('ingredients', __name__)

@ingredients_bp.route('/ingredients')
@login_required
def ingredient_list():
    ingredients = Ingredient.query.all()
    units = InventoryUnit.query.all()
    return render_template('ingredients.html', ingredients=ingredients, units=units)

@ingredients_bp.route('/ingredients/add', methods=['POST'])
@login_required
def add_ingredient():
    name = request.form.get('name')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    db.session.add(Ingredient(name=name, quantity=quantity, unit=unit))
    db.session.commit()
    flash('Ingredient added.')
    return redirect(url_for('ingredients.ingredient_list'))

@ingredients_bp.route('/ingredients/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    if request.method == 'POST':
        ing.quantity = float(request.form.get('quantity'))
        ing.unit = request.form.get('unit')
        db.session.commit()
        flash('Ingredient updated.')
        return redirect(url_for('ingredients.ingredient_list'))
    units = InventoryUnit.query.all()
    return render_template('update_ingredient.html', ing=ing, units=units)

@ingredients_bp.route('/ingredients/delete/<int:id>')
@login_required
def delete_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    db.session.delete(ing)
    db.session.commit()
    flash('Ingredient deleted.')
    return redirect(url_for('ingredients.ingredient_list'))
