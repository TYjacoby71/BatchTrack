
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from models import db, Batch, Recipe, Product, BatchTimer
from datetime import datetime

from . import batches_bp

@batches_bp.route('/')
@login_required
def list_batches():
    query = Batch.query.order_by(Batch.started_at.desc())
    batches = query.all()
    all_recipes = Recipe.query.order_by(Recipe.name).all()
    return render_template('batches/list_batches.html', batches=batches, all_recipes=all_recipes)

@batches_bp.route('/start', methods=['GET', 'POST'])
@login_required
def start_batch():
    if request.method == 'POST':
        recipe_id = request.form.get('recipe_id')
        if recipe_id:
            batch = Batch(recipe_id=recipe_id, status='in_progress')
            db.session.add(batch)
            db.session.commit()
            return redirect(url_for('batches.view_batch', batch_id=batch.id))
    recipes = Recipe.query.all()
    return render_template('batches/start_batch.html', recipes=recipes)
