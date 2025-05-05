from flask import render_template
from flask_login import login_required
from . import timers_bp

@timers_bp.route('/')
@login_required
def list_timers():
    return render_template('timer_list.html')