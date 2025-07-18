
from flask import request, jsonify, flash
from flask_login import login_required, current_user
from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils
from ...models import Organization

def update_organization_timezone():
    """Update organization's default timezone"""
    if not current_user.is_authenticated or not current_user.organization:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if current_user.organization.owner_id != current_user.id:
        return jsonify({'error': 'Only organization owner can update timezone'}), 403
    
    data = request.get_json()
    timezone = data.get('timezone')
    
    if not timezone:
        return jsonify({'error': 'Timezone is required'}), 400
    
    if timezone not in TimezoneUtils.get_available_timezones():
        return jsonify({'error': 'Invalid timezone selected'}), 400
    
    try:
        current_user.organization.default_timezone = timezone
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Organization timezone updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update timezone: {str(e)}'}), 500
