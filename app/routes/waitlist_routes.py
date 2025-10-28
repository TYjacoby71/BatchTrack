
from flask import Blueprint, request, jsonify
import json
import os
from datetime import datetime

waitlist_bp = Blueprint('waitlist', __name__)

@waitlist_bp.route('/api/waitlist', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submissions - save to JSON only"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data or not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400

        # Create waitlist entry
        waitlist_entry = {
            'email': data.get('email'),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'business_type': data.get('business_type', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'homepage'
        }

        # Save to JSON file (persistent storage)
        waitlist_file = 'data/waitlist.json'
        
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        waitlist = []

        # Load existing waitlist
        if os.path.exists(waitlist_file):
            try:
                with open(waitlist_file, 'r') as f:
                    waitlist = json.load(f)
            except (json.JSONDecodeError, IOError):
                waitlist = []

        # Check if email already exists
        if any(entry.get('email') == waitlist_entry['email'] for entry in waitlist):
            return jsonify({'message': 'Email already on waitlist'}), 200

        # Add new entry
        waitlist.append(waitlist_entry)

        # Save updated waitlist
        with open(waitlist_file, 'w') as f:
            json.dump(waitlist, f, indent=2)

        return jsonify({'message': 'Successfully joined waitlist'}), 200

    except Exception as e:
        import traceback
        print(f"Waitlist error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e) if hasattr(e, '__str__') else 'Unknown error'
        }), 500
