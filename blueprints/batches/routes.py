
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import Batch, Recipe, BatchIngredient, InventoryItem
from . import batches_bp
from app import db

@batches_bp.route('/')
@login_required
def list_batches():
    query = Batch.query.order_by(Batch.started_at.desc())
    visible_columns = request.args.get('visible_columns', ['recipe', 'timestamp', 'total_cost', 'product_quantity', 'tags'])
    
    status = request.args.get('status')
    recipe_id = request.args.get('recipe_id')
    start = request.args.get('start')
    end = request.args.get('end')

    if status:
        query = query.filter_by(status=status)
    if recipe_id:
        query = query.filter_by(recipe_id=recipe_id)
    if start:
        query = query.filter(Batch.timestamp >= start)
    if end:
        query = query.filter(Batch.timestamp <= end)

    batches = query.all()
    all_recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('batches_list.html', batches=batches, all_recipes=all_recipes, visible_columns=visible_columns)

@batches_bp.route('/in-progress/<batch_identifier>')
@login_required
def view_batch_in_progress(batch_identifier):
    batch = Batch.query.get_or_404(batch_identifier)
    
    # Calculate ingredient costs
    total_cost = 0
    ingredient_costs = []
    
    ingredients = BatchIngredient.query.filter_by(batch_id=batch.id).all()
    
    for batch_ing in ingredients:
        ingredient = InventoryItem.query.get(batch_ing.ingredient_id)
        if ingredient:
            cost_per_unit = ingredient.cost_per_unit or 0
            line_cost = round(batch_ing.amount_used * cost_per_unit, 2)
            total_cost += line_cost
            
            ingredient_costs.append({
                'name': ingredient.name,
                'used': batch_ing.amount_used,
                'unit': batch_ing.unit,
                'cost_per_unit': cost_per_unit,
                'line_cost': line_cost
            })

    return render_template('batch_in_progress.html', 
                         batch=batch,
                         ingredients=ingredients,
                         ingredient_costs=ingredient_costs,
                         batch_cost=total_cost)
