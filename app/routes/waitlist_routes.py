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

@waitlist_bp.route('/join', methods=['POST'])
def join_waitlist():
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        if not data or 'email' not in data:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        email = data['email'].strip().lower()

        # Basic email validation
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Valid email is required'}), 400

        # Load existing waitlist
        waitlist_data = load_waitlist()

        # Check if already exists
        if email in waitlist_data['emails']:
            return jsonify({'success': True, 'message': 'Already on waitlist'}), 200

        # Add to waitlist
        waitlist_data['emails'].append(email)
        waitlist_data['count'] = len(waitlist_data['emails'])

        # Save updated waitlist
        save_waitlist(waitlist_data)

        return jsonify({
            'success': True,
            'message': 'Successfully added to waitlist',
            'position': len(waitlist_data['emails'])
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500