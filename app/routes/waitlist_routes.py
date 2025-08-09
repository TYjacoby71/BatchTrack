from flask import Blueprint, request, jsonify
import json
import os
from datetime import datetime
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

waitlist_bp = Blueprint('waitlist', __name__)

# Helper function to load waitlist data
def load_waitlist():
    waitlist_file = 'data/waitlist.json'
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(waitlist_file):
        return {'emails': [], 'count': 0}
    try:
        with open(waitlist_file, 'r') as f:
            content = f.read()
            if not content:
                return {'emails': [], 'count': 0}
            data = json.loads(content)
            # Ensure expected keys exist
            if 'emails' not in data:
                data['emails'] = []
            if 'count' not in data:
                data['count'] = len(data['emails'])
            return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading waitlist file {waitlist_file}: {e}")
        return {'emails': [], 'count': 0}

# Helper function to save waitlist data
def save_waitlist(data):
    waitlist_file = 'data/waitlist.json'
    try:
        with open(waitlist_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Waitlist data saved. Current count: {data.get('count', 0)}")
    except IOError as e:
        logger.error(f"Error saving waitlist file {waitlist_file}: {e}")

# Placeholder for is_valid_email function if it were defined elsewhere
def is_valid_email(email):
    # Basic email validation (can be expanded)
    return '@' in email and '.' in email

# Helper function to check if email is on waitlist
def is_email_on_waitlist(email):
    waitlist_data = load_waitlist()
    return email in waitlist_data['emails']

# Placeholder for add_to_waitlist function if it were defined elsewhere
def add_to_waitlist(email, maker_type):
    waitlist_data = load_waitlist()
    if email in waitlist_data['emails']:
        return False, "Email already on waitlist."
    waitlist_data['emails'].append(email)
    waitlist_data['count'] = len(waitlist_data['emails'])
    save_waitlist(waitlist_data)
    return True, "Successfully added to waitlist."

@waitlist_bp.route('/api/waitlist/join', methods=['POST'])
def api_join_waitlist():
    """API endpoint for joining waitlist"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        email = data.get('email', '').strip().lower()
        maker_type = data.get('maker_type', '').strip()

        if not email or not maker_type:
            return jsonify({'success': False, 'error': 'Email and maker type required'}), 400

        if not is_valid_email(email):
            return jsonify({'success': False, 'error': 'Invalid email format'}), 400

        success, message = add_to_waitlist(email, maker_type)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        logger.error(f"Error in api_join_waitlist: {e}") # Added logging for unexpected errors
        return jsonify({'success': False, 'error': 'Failed to join waitlist'}), 500

@waitlist_bp.route('/api/join', methods=['POST'])
def api_join_waitlist():
    """API endpoint for joining waitlist"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        email = data.get('email', '').strip()
        maker_type = data.get('maker_type', '').strip()

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Check if email already exists
        if is_email_on_waitlist(email):
            return jsonify({'success': False, 'error': 'Email already on waitlist'}), 400

        # Add to waitlist
        success = add_to_waitlist(email, maker_type)
        if success:
            return jsonify({'success': True, 'message': 'Successfully added to waitlist'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add to waitlist'}), 500

    except Exception as e:
        print(f"Waitlist API error: {e}")
        return jsonify({'success': False, 'error': 'Server error occurred'}), 500

@waitlist_bp.route('/join', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submission - redirect to API"""
    try:
        data = request.get_json() or request.form.to_dict()
        email = data.get('email', '').strip()
        maker_type = data.get('maker_type', data.get('businessType', '')).strip()

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Check if email already exists
        if is_email_on_waitlist(email):
            return jsonify({'success': False, 'error': 'Email already on waitlist'}), 400

        # Add to waitlist
        success = add_to_waitlist(email, maker_type)
        if success:
            return jsonify({'success': True, 'message': 'Successfully added to waitlist'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add to waitlist'}), 500

    except Exception as e:
        print(f"Waitlist error: {e}")
        return jsonify({'success': False, 'error': 'Server error occurred'}), 500