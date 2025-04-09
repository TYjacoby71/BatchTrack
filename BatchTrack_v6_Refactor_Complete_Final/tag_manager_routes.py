
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, Batch

tag_bp = Blueprint('tags', __name__)

def extract_tags(model):
    tag_map = {}
    entries = model.query.all()
    for entry in entries:
        if entry.tags:
            for tag in entry.tags.split(','):
                tag = tag.strip().lower()
                if tag:
                    tag_map[tag] = tag_map.get(tag, 0) + 1
    return tag_map

@tag_bp.route('/tags/manage', methods=['GET', 'POST'])
@login_required
def manage_tags():
    recipe_tags = extract_tags(Recipe)
    batch_tags = extract_tags(Batch)

    combined = {}
    for tag, count in {**recipe_tags, **batch_tags}.items():
        combined[tag] = recipe_tags.get(tag, 0) + batch_tags.get(tag, 0)

    return render_template('tag_manager.html', tags=combined)
