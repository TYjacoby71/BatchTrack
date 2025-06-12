
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from datetime import datetime
import json
import os
from . import faults_bp

@faults_bp.route('/logs')
@login_required
def fault_logs():
    """Display fault logs"""
    FAULT_LOG_PATH = 'faults.json'
    faults = []
    
    if os.path.exists(FAULT_LOG_PATH):
        try:
            with open(FAULT_LOG_PATH, 'r') as f:
                faults = json.load(f)
                # Sort faults by timestamp in descending order
                faults.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        except json.JSONDecodeError:
            flash('Error reading fault log file', 'error')
            faults = []
    
    return render_template('fault_log.html', logs=faults)

@faults_bp.route('/add_fault', methods=['POST'])
@login_required
def add_fault():
    """Add new fault log entry"""
    try:
        from fault_log_utils import log_fault
        
        message = request.form.get('message')
        severity = request.form.get('severity', 'info')
        
        success = log_fault(message, {'severity': severity}, 'manual')
        
        if success:
            flash('Fault log added successfully', 'success')
        else:
            flash('Error adding fault log', 'error')
    except Exception as e:
        flash(f'Error adding fault log: {str(e)}', 'error')
    
    return redirect(url_for('faults.fault_logs'))

@faults_bp.route('/clear_logs', methods=['POST'])
@login_required
def clear_logs():
    """Clear all fault logs"""
    try:
        FAULT_LOG_PATH = 'faults.json'
        if os.path.exists(FAULT_LOG_PATH):
            with open(FAULT_LOG_PATH, 'w') as f:
                json.dump([], f)
        flash('All fault logs cleared', 'success')
    except Exception as e:
        flash(f'Error clearing logs: {str(e)}', 'error')
    
    return redirect(url_for('faults.fault_logs'))
