from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import Forbidden

from ...extensions import db
from ...services.community_scout_service import CommunityScoutService

community_scout_api_bp = Blueprint('community_scout_api_bp', __name__)


def _require_developer():
    if not current_user.is_authenticated or current_user.user_type != 'developer':
        raise Forbidden("Developer access required for Community Scout.")


@community_scout_api_bp.route('/batches/next', methods=['GET'])
@login_required
def community_scout_next_batch():
    _require_developer()
    batch = CommunityScoutService.get_next_batch(claimed_by_user_id=current_user.id)
    payload = CommunityScoutService.serialize_batch(batch)
    db.session.commit()
    return jsonify({'success': True, 'batch': payload})


@community_scout_api_bp.route('/candidates/<int:candidate_id>/promote', methods=['POST'])
@login_required
def community_scout_promote(candidate_id: int):
    _require_developer()
    data = request.get_json(force=True) or {}
    payload = data.get('global_item_payload') or {}
    try:
        result = CommunityScoutService.promote_candidate(candidate_id, payload, current_user.id)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@community_scout_api_bp.route('/candidates/<int:candidate_id>/link', methods=['POST'])
@login_required
def community_scout_link(candidate_id: int):
    _require_developer()
    data = request.get_json(force=True) or {}
    global_item_id = data.get('global_item_id')
    if not global_item_id:
        return jsonify({'success': False, 'error': 'global_item_id is required'}), 400
    try:
        result = CommunityScoutService.link_candidate(candidate_id, int(global_item_id), current_user.id)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@community_scout_api_bp.route('/candidates/<int:candidate_id>/reject', methods=['POST'])
@login_required
def community_scout_reject(candidate_id: int):
    _require_developer()
    data = request.get_json(force=True) or {}
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'success': False, 'error': 'reason is required'}), 400
    try:
        result = CommunityScoutService.reject_candidate(candidate_id, reason, current_user.id)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400


@community_scout_api_bp.route('/candidates/<int:candidate_id>/flag', methods=['POST'])
@login_required
def community_scout_flag(candidate_id: int):
    _require_developer()
    data = request.get_json(force=True) or {}
    flag_payload = data or {}
    try:
        result = CommunityScoutService.flag_candidate(candidate_id, flag_payload, current_user.id)
        return jsonify({'success': True, **result})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(exc)}), 400
