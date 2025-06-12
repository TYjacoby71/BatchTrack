
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import FaultLog, db
from datetime import datetime
from . import faults_bp

@faults_bp.route('/logs')
@login_required
def fault_logs():
    """Display fault logs"""
    logs = FaultLog.query.order_by(FaultLog.timestamp.desc()).all()
    return render_template('fault_log.html', logs=logs)

@faults_bp.route('/add_fault', methods=['POST'])
@login_required
def add_fault():
    """Add new fault log entry"""
    try:
        fault = FaultLog(
            message=request.form.get('message'),
            severity=request.form.get('severity', 'info'),
            timestamp=datetime.utcnow()
        )
        db.session.add(fault)
        db.session.commit()
        flash('Fault log added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding fault log: {str(e)}', 'error')
    
    return redirect(url_for('faults.fault_logs'))

@faults_bp.route('/clear_logs', methods=['POST'])
@login_required
def clear_logs():
    """Clear all fault logs"""
    try:
        FaultLog.query.delete()
        db.session.commit()
        flash('All fault logs cleared', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing logs: {str(e)}', 'error')
    
    return redirect(url_for('faults.fault_logs'))
