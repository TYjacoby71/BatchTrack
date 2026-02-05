from flask import jsonify, render_template, request, url_for
from flask_login import login_required, current_user
from app.utils.permissions import require_permission

from app.extensions import db
from app.models import Organization
from app.services.drawers.payloads import build_drawer_payload
from app.services.retention_service import RetentionService

from .. import drawers_bp, register_cadence_check, register_drawer_action


register_drawer_action(
    'retention.modal',
    description='Blocker drawer that surfaces recipes pending retention acknowledgement.',
    endpoint='drawers.retention_modal',
    success_event='retention.acknowledged',
)


def _build_retention_payload(count: int | None = None):
    payload = build_drawer_payload(
        modal_url=url_for('drawers.retention_modal'),
        error_type='retention',
        error_code='AT_RISK_ITEMS',
        success_event='retention.acknowledged',
    )
    if count is not None:
        payload['metadata'] = {'count': count}
    return payload


def _resolve_current_org():
    try:
        org_id = getattr(current_user, 'organization_id', None)
    except Exception:
        org_id = None
    if not org_id:
        return None
    try:
        return db.session.get(Organization, org_id)
    except Exception:
        return None


def _get_retention_items():
    org = _resolve_current_org()
    if not org:
        return []
    return RetentionService.get_pending_drawer_items(org)


@register_cadence_check('retention')
def retention_cadence_check():
    """Return a drawer payload if retention items need acknowledgement."""
    if not current_user.is_authenticated:
        return None

    items = _get_retention_items()
    if not items:
        return None
    payload = _build_retention_payload(len(items))
    payload.setdefault('retry', {'operation': 'retention.refresh', 'data': {}})
    return payload


@drawers_bp.route('/retention/check', methods=['GET'])
@login_required
@require_permission('recipes.delete')
def retention_check():
    """Direct polling endpoint (used by tests) for retention drawers."""
    items = _get_retention_items()
    payload = _build_retention_payload(len(items)) if items else None
    return jsonify({'needs_drawer': bool(items), 'count': len(items), 'drawer_payload': payload})


@drawers_bp.route('/retention/modal', methods=['GET'])
@login_required
@require_permission('recipes.delete')
def retention_modal():
    org = _resolve_current_org()
    items = RetentionService.get_pending_drawer_items(org) if org else []
    html = render_template('components/drawer/retention_modal.html', items=items)
    return jsonify({'success': True, 'modal_html': html})


@drawers_bp.route('/retention/acknowledge', methods=['POST'])
@login_required
@require_permission('recipes.delete')
def retention_acknowledge():
    org = _resolve_current_org()
    items = RetentionService.get_pending_drawer_items(org) if org else []
    ids = [recipe.id for recipe in items]
    created, skipped = RetentionService.acknowledge_and_queue(org, ids)
    return jsonify({'success': True, 'queued': created, 'skipped': skipped})


@drawers_bp.route('/retention/export', methods=['GET'])
@login_required
@require_permission('recipes.delete')
def retention_export():
    org = _resolve_current_org()
    export_format = request.args.get('format', 'json')
    mimetype, content = RetentionService.export_at_risk(org, export_format)
    return content, 200, {'Content-Type': mimetype}
