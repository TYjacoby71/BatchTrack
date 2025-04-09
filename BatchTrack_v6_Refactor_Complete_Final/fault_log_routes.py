
from flask import Blueprint, render_template
import json
import os

faults_bp = Blueprint('faults', __name__)
FAULT_LOG_PATH = 'faults.json'

@faults_bp.route('/logs/faults')
def view_fault_log():
    faults = []
    if os.path.exists(FAULT_LOG_PATH):
        with open(FAULT_LOG_PATH, 'r') as f:
            try:
                faults = json.load(f)
            except json.JSONDecodeError:
                faults = []
    return render_template('fault_log.html', faults=faults)
