# This file has been merged into blueprints/recipes/routes.py
# All routes are now handled by the blueprint version
@recipes_bp.route('/recipes/<int:recipe_id>/edit', methods=['GET'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    containers = InventoryItem.query.filter_by(type='container').all()
    return render_template('recipe_form.html', recipe=recipe, containers=containers)