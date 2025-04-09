
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit
from datetime import datetime
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/batches/start', methods=['GET', 'POST'])
@login_required
def start_batch():
    if request.method == 'POST':
        recipe_id = request.form.get('recipe_id')
        scale = float(request.form.get('scale', 1.0))
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            flash('Invalid recipe selected')
            return redirect(url_for('batches.start_batch'))

        # Generate label_code
        year = datetime.utcnow().year
        count = Batch.query.filter_by(recipe_name=recipe.name).count() + 1
        label_code = f"{recipe.label_prefix}-{year}{count:02d}"

        batch = Batch(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            scale=scale,
            label_code=label_code
        )
        db.session.add(batch)
        db.session.commit()
        return redirect(url_for('batches.view_batch_in_progress'))

    recipes = Recipe.query.all()
    return render_template('start_batch.html', recipes=recipes)

@batches_bp.route('/batches/in-progress')
@login_required
def view_batch_in_progress():
    batch = Batch.query.filter(Batch.total_cost == 0).first()
    if not batch:
        flash('No batch in progress.')
        return redirect(url_for('home'))
    return render_template('batch_in_progress.html', batch=batch)

@batches_bp.route('/batches/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    action = request.form.get('action')
    batch.notes = request.form.get('notes')
    batch.tags = request.form.get('tags')
    unit = request.form.get('product_unit')
    quantity = int(request.form.get('product_quantity', 1))

    if action == 'fail':
        batch.total_cost = 0
        db.session.commit()
        flash("Batch marked as failed.")
        return redirect(url_for('home'))

    cost = 5.0 * batch.scale
    batch.total_cost = cost

    img_file = request.files.get('product_image')
    image_path = None
    if img_file and img_file.filename:
        filename = f"prod_{uuid.uuid4().hex}_{secure_filename(img_file.filename)}"
        save_path = os.path.join('static/product_images', filename)
        img_file.save(save_path)
        image_path = filename

    product = Product(
        batch_id=batch.id,
        name=batch.recipe_name,
        label_code=batch.label_code,
        image=image_path,
        expiration_date=datetime.utcnow().date(),
        quantity=quantity,
        unit=unit
    )
    db.session.add(product)
    db.session.commit()
    flash("Batch finished and product created.")
    return redirect(url_for('home'))

@batches_bp.route('/batches/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash("Batch canceled and inventory restored.")
    return redirect(url_for('home'))
