
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..models import db, Tag, Recipe

tag_manager_bp = Blueprint('tags', __name__)

@tag_manager_bp.route('/tags/manage')
@login_required
def manage_tags():
    # Get scoped tags
    tags_query = Tag.query
    if current_user.organization_id:
        tags_query = tags_query.filter_by(organization_id=current_user.organization_id)
    tags = tags_query.all()
    
    # Get scoped recipes
    recipes_query = Recipe.query
    if current_user.organization_id:
        recipes_query = recipes_query.filter_by(organization_id=current_user.organization_id)
    recipes = recipes_query.all()
    
    return render_template('tag_manager.html', tags=tags, recipes=recipes)

@tag_manager_bp.route('/tags/add', methods=['POST'])
@login_required
def add_tag():
    name = request.form.get('name')
    if name:
        tag = Tag(
            name=name,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(tag)
        db.session.commit()
        flash('Tag added successfully')
    return redirect(url_for('tags.manage_tags'))

@tag_manager_bp.route('/tags/delete/<int:tag_id>')
@login_required
def delete_tag(tag_id):
    # Get scoped tag
    query = Tag.query
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)
    tag = query.filter_by(id=tag_id).first_or_404()
    
    db.session.delete(tag)
    db.session.commit()
    flash('Tag deleted successfully')
    return redirect(url_for('tags.manage_tags'))
