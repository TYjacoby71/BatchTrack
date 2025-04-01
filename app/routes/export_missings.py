
from flask import Blueprint, request, render_template, Response
import csv
from io import StringIO

export_bp = Blueprint('export', __name__)

@export_bp.route('/missing/export/csv', methods=['POST'])
def export_missing_csv():
    data = request.json
    if not data or 'items' not in data:
        return "No data provided", 400

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Needed Quantity', 'Unit'])

    for item in data['items']:
        writer.writerow([item['name'], item['total'], item['unit']])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=missing_items.csv"
    return response

@export_bp.route('/missing/export/print', methods=['POST'])
def export_missing_print():
    items = request.json.get('items', [])
    return render_template("print_missing.html", items=items)
