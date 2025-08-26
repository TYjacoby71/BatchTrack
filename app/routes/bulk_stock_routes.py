from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from ..models import db, Recipe, InventoryItem
from ..services.unit_conversion import ConversionEngine
from sqlalchemy.exc import SQLAlchemyError
import io
import csv
from flask import make_response

bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    try:
        recipes = Recipe.scoped().all()
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

            from app.services.stock_check.core import UniversalStockCheckService
            uscs = UniversalStockCheckService()
            recipe_configs = [{'recipe_id': int(rid), 'scale': scale} for rid in selected_ids]
            bulk_results = uscs.check_bulk_recipes(recipe_configs)
            
            if bulk_results['success']:
                # Aggregate results from USCS
                ingredient_totals = {}
                
                for rid, result in bulk_results['results'].items():
                    if result['success']:
                        stock_data = result.get('stock_check', [])
                        
                        for item in stock_data:
                            name = item.get('name', item.get('item_name', 'Unknown'))
                            needed = item.get('needed', item.get('needed_quantity', 0))
                            unit = item.get('unit', item.get('needed_unit', 'ml'))
                            available = item.get('available', item.get('available_quantity', 0))
                            
                            key = (name, unit)
                            if key not in ingredient_totals:
                                ingredient_totals[key] = {
                                    'name': name,
                                    'unit': unit,
                                    'needed': 0,
                                    'available': available
                                }
                            ingredient_totals[key]['needed'] += needed
                
                # Determine status for each ingredient
                for item in ingredient_totals.values():
                    if item['available'] >= item['needed']:
                        item['status'] = 'OK'
                    elif item['available'] > 0:
                        item['status'] = 'LOW'
                    else:
                        item['status'] = 'NEEDED'
                
                summary = list(ingredient_totals.values())
                session['bulk_summary'] = summary
            else:
                flash('Bulk stock check failed', 'error')

        return render_template('bulk_stock_check.html', recipes=recipes, summary=summary)
    except Exception as e:
        flash(f'Error checking stock: {str(e)}')
        return redirect(url_for('bulk_stock.bulk_stock_check'))

@bulk_stock_bp.route('/bulk-check/csv')
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
    except ValueError as e:
        flash(f"Bulk stock processing failed: {e}", "warning")
        return redirect(request.referrer or url_for('stock.bulk_check'))
    except SQLAlchemyError as e:
        flash("Database error exporting CSV.", "danger")
        return redirect(url_for('bulk_stock.bulk_stock_check'))