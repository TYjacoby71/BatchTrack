
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from models import db, Recipe, Ingredient
from stock_check_utils import check_stock_for_recipe
from unit_conversion_utils import convert_units

bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/stock/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    try:
        recipes = Recipe.query.all()
        summary = {}
        selected_ids = []

        if request.method == 'POST':
            selected_ids = request.form.getlist('recipe_ids')
            if not selected_ids:
                flash('Please select at least one recipe')
                return redirect(url_for('bulk_stock.bulk_stock_check'))
                
            try:
                scale = float(request.form.get('scale', 1.0))
                if scale <= 0:
                    flash('Scale must be greater than 0')
                    return redirect(url_for('bulk_stock.bulk_stock_check'))
            except ValueError:
                flash('Invalid scale value')
                return redirect(url_for('bulk_stock.bulk_stock_check'))
                
            session['bulk_recipe_ids'] = selected_ids
            session['bulk_scale'] = scale

            for rid in selected_ids:
                recipe = Recipe.query.get(int(rid))
                if not recipe:
                    continue
                results, _ = check_stock_for_recipe(recipe, scale)

                for row in results:
                    name = row['name']
                    needed = row['needed']
                    from_unit = row.get('unit') or 'ml'
                    ingredient = Ingredient.query.filter_by(name=name).first()

                    if not ingredient:
                        continue

                    to_unit = ingredient.unit
                    try:
                        needed_converted = convert_units(needed, from_unit, to_unit)
                    except Exception:
                        needed_converted = needed
                        to_unit = from_unit

                    key = (name, to_unit)
                    if key not in summary:
                        summary[key] = {
                            'name': name,
                            'unit': to_unit,
                            'needed': 0,
                            'available': ingredient.quantity if ingredient else 0
                        }
                    summary[key]['needed'] += needed_converted

            for val in summary.values():
                if val['available'] >= val['needed']:
                    val['status'] = 'OK'
                elif val['available'] > 0:
                    val['status'] = 'LOW'
                else:
                    val['status'] = 'NEEDED'

            summary = list(summary.values())
            session['bulk_summary'] = summary

        return render_template('bulk_stock_check.html', recipes=recipes, summary=summary)
    except Exception as e:
        flash(f'Error checking stock: {str(e)}')
        return redirect(url_for('bulk_stock.bulk_stock_check'))

@bulk_stock_bp.route('/stock/bulk-check/csv')
@login_required
def export_shopping_list_csv():
    try:
        summary = session.get('bulk_summary', [])
        if not summary:
            flash('No stock check results available')
            return redirect(url_for('bulk_stock.bulk_stock_check'))
            
        missing = [item for item in summary if item['status'] in ['LOW', 'NEEDED']]
        if not missing:
            flash('No items need restocking')
            return redirect(url_for('bulk_stock.bulk_stock_check'))

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Ingredient', 'Needed', 'Available', 'Unit', 'Status'])
        for item in missing:
            cw.writerow([item['name'], item['needed'], item['available'], item['unit'], item['status']])

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=shopping_list.csv"
        output.headers["Content-type"] = "text/csv"
        return output
    except Exception as e:
        flash(f'Error exporting CSV: {str(e)}')
        return redirect(url_for('bulk_stock.bulk_stock_check'))
