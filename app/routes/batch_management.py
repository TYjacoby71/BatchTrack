
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime

batch_mgmt_bp = Blueprint('batch_management', __name__)

@batch_mgmt_bp.route('/start-batch/<int:recipe_id>', methods=['GET', 'POST'])
def start_batch(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        flash('Recipe not found')
        return redirect('/recipes')
        
    scale = float(request.args.get('scale', 1))
    
    if request.method == 'POST':
        # Create new batch
        new_batch = {
            'id': len(data.get('batches', [])) + 1,
            'recipe_id': recipe_id,
            'recipe_name': recipe['name'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'completed': False,
            'scale': scale,
            'ingredients': []
        }
        
        # Scale ingredients
        for ingredient in recipe.get('ingredients', []):
            new_batch['ingredients'].append({
                'name': ingredient['name'],
                'quantity': float(ingredient['quantity']) * scale,
                'unit': ingredient['unit']
            })
            
        if 'batches' not in data:
            data['batches'] = []
        data['batches'].append(new_batch)
        save_data(data)
        
        return redirect(f'/batches/in-progress/{new_batch["id"]}')
        
    return render_template('start_batch.html', recipe=recipe, scale=scale)
