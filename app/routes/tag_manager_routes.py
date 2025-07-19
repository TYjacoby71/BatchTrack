from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ..models import db, Tag

tag_manager_bp = Blueprint('tag_manager', __name__)

@tag_manager_bp.route('/tag-manager')
@login_required
def tag_manager():
    tags = Tag.scoped().all()
    return render_template('tag_manager.html', tags=tags)

@tag_manager_bp.route('/api/tags', methods=['GET'])
@login_required
def get_tags():
    tags = Tag.scoped().filter_by(is_active=True).all()
    return jsonify([{
        'id': tag.id,
        'name': tag.name,
        'color': tag.color,
        'description': tag.description
    } for tag in tags])

@tag_manager_bp.route('/api/tags', methods=['POST'])
@login_required
def create_tag():
    data = request.get_json()

    tag = Tag(
        name=data['name'],
        color=data.get('color', '#6c757d'),
        description=data.get('description', ''),
        organization_id=current_user.organization_id,
        created_by=current_user.id
    )

    db.session.add(tag)
    db.session.commit()

    return jsonify({'success': True, 'tag_id': tag.id})

@tag_manager_bp.route('/api/tags/<int:tag_id>', methods=['PUT'])
@login_required
def update_tag(tag_id):
    tag = Tag.scoped().filter_by(id=tag_id).first_or_404()
    data = request.get_json()

    tag.name = data['name']
    tag.color = data.get('color', tag.color)
    tag.description = data.get('description', tag.description)

    db.session.commit()

    return jsonify({'success': True})

@tag_manager_bp.route('/api/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def delete_tag(tag_id):
    tag = Tag.scoped().filter_by(id=tag_id).first_or_404()
    tag.is_active = False
    db.session.commit()

    return jsonify({'success': True})