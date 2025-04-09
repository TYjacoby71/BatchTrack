
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Batch, Recipe, Product, ProductUnit
from datetime import datetime
import uuid, os
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('/batches')
@login_required
def list_batches():
    batches = Batch.query.order_by(Batch.timestamp.desc()).all()
    return render_template('batches_list.html', batches=batches)

@batches_bp.route('/batches/start', methods=['GET', 'POST'])
@login_required
def start_batch():
    if request.method == 'POST':
        try:
            recipe_id = request.form.get('recipe_id')
            scale = float(request.form.get('scale', 1.0))
            if scale <= 0:
                flash('Scale must be greater than 0')
                return redirect(url_for('batches.start_batch'))
                
            recipe = Recipe.query.get_or_404(recipe_id)
            
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
        except Exception as e:
            flash(f'Error starting batch: {str(e)}')
            return redirect(url_for('batches.start_batch'))

    recipes = Recipe.query.all()
    return render_template('start_batch.html', recipes=recipes)

@batches_bp.route('/batches/in-progress/<int:batch_id>')
@login_required
def view_batch_in_progress(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    if batch.total_cost is not None:
        flash('This batch is already completed.')
        return redirect(url_for('batches.list_batches'))
    product_units = ProductUnit.query.all()
    return render_template('batch_in_progress.html', batch=batch, product_units=product_units)

@batches_bp.route('/batches/in-progress/<int:batch_id>/notes', methods=['POST'])
@login_required
def update_batch_notes(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    batch.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Notes updated successfully.')
    return redirect(url_for('batches.view_batch_in_progress', batch_id=batch_id))

@batches_bp.route('/batches/finish/<int:batch_id>', methods=['POST'])
@login_required
def finish_batch(batch_id):
    try:
        batch = Batch.query.get_or_404(batch_id)
        action = request.form.get('action')
        batch.notes = request.form.get('notes')
        batch.tags = request.form.get('tags')
        unit = request.form.get('product_unit')
        
        try:
            quantity = int(request.form.get('product_quantity', 1))
            if quantity <= 0:
                flash('Quantity must be greater than 0')
                return redirect(url_for('batches.view_batch_in_progress'))
        except ValueError:
            flash('Invalid quantity value')
            return redirect(url_for('batches.view_batch_in_progress'))

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
    except Exception as e:
        flash(f'Error finishing batch: {str(e)}')
        return redirect(url_for('batches.view_batch_in_progress'))

@batches_bp.route('/batches/cancel/<int:batch_id>', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash("Batch canceled and inventory restored.")
    return redirect(url_for('home'))
