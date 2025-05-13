
from flask import Blueprint, redirect, url_for, flash, render_template, request, jsonify
from flask_login import login_required
from models import db, BatchTimer
from datetime import datetime

timers_bp = Blueprint('timers', __name__, url_prefix='/timers')

@timers_bp.route('/start', methods=['POST'])
@login_required
def start_timer():
    timer_id = request.form.get('timer_id')
    timer = BatchTimer.query.get_or_404(timer_id)
    
    if not timer.start_time:
        timer.start_time = datetime.utcnow()
        timer.status = 'running'
        db.session.commit()
        
    return jsonify({
        'status': 'success',
        'start_time': timer.start_time.isoformat() if timer.start_time else None
    })

@timers_bp.route('/list')
@login_required
def list_timers():
    timers = BatchTimer.query.all()
    return render_template('timer_list.html', timers=timers)

@timers_bp.route('/complete/<int:timer_id>', methods=['POST'])
@login_required
def complete_timer(timer_id):
    timer = BatchTimer.query.get_or_404(timer_id)
    timer.completed = True
    db.session.commit()
    flash("Timer marked complete.")
    return redirect(url_for('batches.view_batch_in_progress', batch_identifier=timer.batch_id))
