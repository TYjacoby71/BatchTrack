from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from models import Recipe
from stock_check_utils import check_recipe_stock
import logging

logger = logging.getLogger(__name__)
bulk_stock_bp = Blueprint('bulk_stock', __name__)

@bulk_stock_bp.route('/stock/bulk-check', methods=['GET', 'POST'])
@login_required
def bulk_stock_check():
    try:
        recipes = Recipe.query.all()
        summary = {}

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

            for rid in selected_ids:
                recipe = Recipe.query.get(int(rid))
                if not recipe:
                    continue

                results, _ = check_recipe_stock(recipe, scale)

                for item in results:
                    key = (item['name'], item['unit'])
                    if key not in summary:
                        summary[key] = item
                    else:
                        summary[key]['needed'] += item['needed']
                        summary[key]['status'] = 'OK' if summary[key]['available'] >= summary[key]['needed'] else 'LOW' if summary[key]['available'] > 0 else 'NEEDED'

            summary = list(summary.values())
            session['bulk_summary'] = summary

        return render_template('bulk_stock_check.html', recipes=recipes, summary=summary)

    except Exception as e:
        logger.exception("Bulk stock check failed")
        flash(f'Error checking stock: {str(e)}')
        return redirect(url_for('bulk_stock.bulk_stock_check'))