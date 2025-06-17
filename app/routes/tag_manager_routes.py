
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Tag, Recipe

tag_bp = Blueprint('tags', __name__)

@tag_bp.route('/tags/manage')
@login_required
def manage_tags():
    tags = Tag.query.all()
    recipes = Recipe.query.all()
    return render_template('tag_manager.html', tags=tags, recipes=recipes)

@tag_bp.route('/tags/add', methods=['POST'])
@login_required
def add_tag():
    name = request.form.get('name')
    if name:
        tag = Tag(name=name)
        db.session.add(tag)
        db.session.commit()
        flash('Tag added successfully')
    return redirect(url_for('tags.manage_tags'))

@tag_bp.route('/tags/delete/<int:tag_id>')
@login_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash('Tag deleted successfully')
    return redirect(url_for('tags.manage_tags'))
