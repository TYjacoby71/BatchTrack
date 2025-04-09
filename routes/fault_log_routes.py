
from flask import Blueprint, render_template, request, flash
from flask_login import login_required
import json
import os
from datetime import datetime
from fault_log_utils import log_fault, FAULT_LOG_PATH

faults_bp = Blueprint('faults', __name__)

@faults_bp.route('/logs/faults')
@login_required
def view_fault_log():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        faults = []
        
        if os.path.exists(FAULT_LOG_PATH):
            with open(FAULT_LOG_PATH, 'r') as f:
                try:
                    faults = json.load(f)
                    # Sort faults by timestamp in descending order
                    faults.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                except json.JSONDecodeError:
                    flash('Error reading fault log file')
                    faults = []
                    
        # Simple pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated_faults = faults[start:end]
        
        return render_template('fault_log.html', 
                             faults=paginated_faults,
                             page=page,
                             has_next=len(faults) > end,
                             has_prev=page > 1)
    except Exception as e:
        flash(f'Error viewing fault log: {str(e)}')
        log_fault('Error viewing fault log', {'error': str(e)})
        return render_template('fault_log.html', faults=[])
