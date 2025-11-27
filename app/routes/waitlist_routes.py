
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from app.utils.json_store import read_json_file, write_json_file

waitlist_bp = Blueprint('waitlist', __name__)

@waitlist_bp.route('/api/waitlist', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submissions - save to JSON only"""
    print("=== WAITLIST ROUTE ACCESSED ===")
    print(f"Request method: {request.method}")
    print(f"Request content type: {request.content_type}")
    print(f"Request data: {request.get_data()}")
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
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'homepage'
        }

        # Save to JSON file (persistent storage)
        waitlist_file = 'data/waitlist.json'

        waitlist = read_json_file(waitlist_file, default=[]) or []

        # Check if email already exists
        if any(entry.get('email') == waitlist_entry['email'] for entry in waitlist):
            return jsonify({'message': 'Email already on waitlist'}), 200

        # Add new entry
        waitlist.append(waitlist_entry)

        # Save updated waitlist
        write_json_file(waitlist_file, waitlist)

        return jsonify({'message': 'Successfully joined waitlist'}), 200

    except Exception as e:
        import traceback
        print(f"Waitlist error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e) if hasattr(e, '__str__') else 'Unknown error'
        }), 500
