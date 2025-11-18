from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from io import BytesIO

from ...models import db, Organization
from ...services.retention_service import RetentionService

retention_bp = Blueprint('retention', __name__, url_prefix='/retention')


@retention_bp.route('/api/check')
@login_required
def check_retention_needed():
    org: Organization | None = current_user.organization
    if not org:
        return jsonify({'needs_drawer': False})
    items = RetentionService.get_pending_drawer_items(org)
    return jsonify({'needs_drawer': len(items) > 0, 'count': len(items)})


@retention_bp.route('/api/modal')
@login_required
def get_retention_modal():
    org: Organization | None = current_user.organization
    items = RetentionService.get_pending_drawer_items(org) if org else []

    html = render_template('components/drawer/retention_modal.html', items=items)

    return jsonify({'success': True, 'modal_html': html})


@retention_bp.route('/api/acknowledge', methods=['POST'])
@login_required
def acknowledge_retention():
    org: Organization | None = current_user.organization
    items = RetentionService.get_pending_drawer_items(org) if org else []
    ids = [r.id for r in items]
    created, skipped = RetentionService.acknowledge_and_queue(org, ids)
    return jsonify({'success': True, 'queued': created, 'skipped': skipped})


@retention_bp.route('/api/export')
@login_required
def export_retention():
    org: Organization | None = current_user.organization
    fmt = request.args.get('format', 'json')
    mimetype, content = RetentionService.export_at_risk(org, fmt)
    return content, 200, {'Content-Type': mimetype}

