
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data

batch_mgmt_bp = Blueprint('batch_mgmt', __name__)

@batch_mgmt_bp.route('/batch/manage')
def manage_batches():
    data = load_data()
    batches = data.get('batches', [])
    return render_template('batches.html', batches=batches)
