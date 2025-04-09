
from flask import Blueprint, render_template, request, make_response, redirect, url_for, session
from flask_login import login_required
from models import db, Recipe
from ingredient_routes import Ingredient
from stock_check_utils import check_stock_for_recipe
from unit_conversion_utils import convert_units
import csv
import io

bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/stock/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    recipes = Recipe.query.all()
    summary = {}

    if request.method == 'POST':
        selected_ids = request.form.getlist('recipe_ids')
        scale = float(request.form.get('scale', 1.0))
        session['bulk_recipe_ids'] = selected_ids
        session['bulk_scale'] = scale

        for rid in selected_ids:
            recipe = Recipe.query.get(int(rid))
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


@bulk_stock_bp.route('/stock/bulk-check/csv')
@login_required
def export_shopping_list_csv():
    summary = session.get('bulk_summary', [])
    missing = [item for item in summary if item['status'] in ['LOW', 'NEEDED']]

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Ingredient', 'Needed', 'Available', 'Unit', 'Status'])
    for item in missing:
        cw.writerow([item['name'], item['needed'], item['available'], item['unit'], item['status']])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=shopping_list.csv"
    output.headers["Content-type"] = "text/csv"
    return output
