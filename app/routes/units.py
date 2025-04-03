
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
import json

unit_bp = Blueprint('units', __name__)

@unit_bp.route('/units', methods=['GET', 'POST'])
def manage_units():
    # Load existing units
    try:
        with open('units.json', 'r') as f:
            units_data = json.load(f)
            count_units = units_data.get('Count', {}).get('units', [])
    except:
        count_units = []
    
    if request.method == 'POST':
        action = request.form.get('action')
        unit_name = request.form.get('unit_name')
        
        if action == 'add' and unit_name:
            if unit_name not in count_units:
                count_units.append(unit_name)
                units_data['Count']['units'] = count_units
                with open('units.json', 'w') as f:
                    json.dump(units_data, f, indent=2)
                flash(f'Added unit: {unit_name}')
            
        elif action == 'remove' and unit_name:
            if unit_name in count_units:
                count_units.remove(unit_name)
                units_data['Count']['units'] = count_units
                with open('units.json', 'w') as f:
                    json.dump(units_data, f, indent=2)
                flash(f'Removed unit: {unit_name}')
                
        return redirect('/units')
        
    return render_template('unit_editor.html', count_units=count_units)
